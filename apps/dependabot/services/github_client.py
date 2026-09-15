"""Read-only GitHub repository client for manifest discovery.

Only two endpoints are used, both ``GET``:

- ``GET /repos/{owner}/{repo}`` → repository metadata (default branch).
- ``GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`` → file content.

Every call authenticates with a per-installation token from
:class:`GitHubInstallationTokenService` (never the App JWT directly).
Security rules mirror the token service: credentials never appear in any
exception message, ``extra`` payload, or log line — only the repository
identity, HTTP status codes, and file paths are logged.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import logging
import re

import httpx

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.services.github_jwt import create_github_app_jwt
from apps.dependabot.services.github_token import (
    GITHUB_ACCEPT_HEADER,
    GITHUB_API_VERSION,
    GITHUB_USER_AGENT,
    GitHubInstallationTokenService,
    load_github_app_config,
)

logger = logging.getLogger(__name__)

MANIFEST_PATH = "itqan-assets.yaml"
LOCKFILE_PATH = "itqan-assets.lock"
ALLOWED_MANIFEST_PATHS = (MANIFEST_PATH, LOCKFILE_PATH)

# Git blob SHAs as returned by the Contents API ``sha`` field are SHA-1
# (40 lowercase hex chars). Uppercase is accepted defensively; anything else
# means the response is not a usable file reference.
_BLOB_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

# The Contents API inlines file content only up to 1 MiB (larger files must
# go through the blob API, which discovery deliberately does not use), so a
# larger payload is refused before decoding.
MAX_DECODED_BYTES = 1024 * 1024


@dataclass(frozen=True)
class GitHubRepoMetadata:
    """Repository metadata needed by discovery."""

    owner: str
    repository_name: str
    default_branch: str


@dataclass(frozen=True)
class DiscoveredFile:
    """One root manifest file as seen through the Contents API.

    ``present`` is False when GitHub answered 404 (file absent — normal, not
    an error). When True but ``content`` is None, the file exists yet could
    not be interpreted (wrong type, bad SHA, unsupported encoding, invalid
    base64, oversized); ``sha`` is then also None and discovery treats the
    side as INVALID rather than absent.
    """

    path: str
    present: bool
    sha: str | None
    content: bytes | None


def _base_headers(installation_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {installation_token}",
        "Accept": GITHUB_ACCEPT_HEADER,
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": GITHUB_USER_AGENT,
    }


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code != 403:
        return False
    if response.headers.get("x-ratelimit-remaining") == "0":
        return True
    try:
        return "rate limit" in response.text.lower()
    except Exception:  # nosec B110 — undecodable body simply is not a rate-limit signal
        return False


def _raise_for_status(response: httpx.Response, *, owner: str, repository_name: str, what: str) -> None:
    """Map transport-level failures to ItqanError. File 404 is handled by callers."""
    if 200 <= response.status_code < 300:
        return
    if response.status_code == 401:
        logger.warning(
            "github_client: authentication failed [owner=%s, repo=%s, what=%s]",
            owner,
            repository_name,
            what,
        )
        raise ItqanError(
            "github_authentication_failed",
            "GitHub rejected the installation credentials.",
            401,
        )
    if _is_rate_limited(response):
        retry_after = response.headers.get("retry-after")
        extra: dict[str, int] = {}
        if retry_after is not None and retry_after.isdigit():
            extra["retry_after_seconds"] = int(retry_after)
        logger.warning(
            "github_client: rate limited [owner=%s, repo=%s, what=%s, status=%d]",
            owner,
            repository_name,
            what,
            response.status_code,
        )
        raise ItqanError(
            "github_rate_limited",
            "GitHub API rate limit exceeded.",
            503,
            extra=extra,
        )
    if response.status_code == 403:
        logger.warning(
            "github_client: access denied [owner=%s, repo=%s, what=%s]",
            owner,
            repository_name,
            what,
        )
        raise ItqanError(
            "github_access_denied",
            "GitHub refused access to the repository.",
            403,
        )
    if response.status_code == 404:
        logger.warning(
            "github_client: repository unavailable [owner=%s, repo=%s, what=%s]",
            owner,
            repository_name,
            what,
        )
        raise ItqanError(
            "github_repository_unavailable",
            "GitHub repository is unavailable.",
            404,
        )
    logger.warning(
        "github_client: upstream error [owner=%s, repo=%s, what=%s, status=%d]",
        owner,
        repository_name,
        what,
        response.status_code,
    )
    raise ItqanError(
        "github_upstream_error",
        f"GitHub request failed (status {response.status_code}).",
        502,
    )


def _decode_contents_payload(payload: object, *, owner: str, repository_name: str, path: str) -> DiscoveredFile:
    """Interpret one Contents API response body as a file (or absence).

    Anything that is not a decodable file object yields ``present`` with
    ``content=None`` (never raises): directories (which arrive as a list),
    submodules, symlinks, SHA/encoding/base64 problems, and oversized
    payloads are all "exists but uninterpretable", which discovery reports
    as INVALID rather than absent.
    """
    unreadable = DiscoveredFile(path=path, present=True, sha=None, content=None)
    if not isinstance(payload, dict):
        # Directories arrive as a list; anything else is equally unusable.
        return unreadable
    if payload.get("type") != "file":
        return unreadable
    if payload.get("path") != path:
        return unreadable
    sha = payload.get("sha")
    if not isinstance(sha, str) or not _BLOB_SHA_RE.match(sha):
        return unreadable
    encoding = payload.get("encoding")
    raw_content = payload.get("content")
    size = payload.get("size", 0)
    if isinstance(size, int) and size > MAX_DECODED_BYTES:
        logger.warning(
            "github_client: file exceeds size bound [owner=%s, repo=%s, path=%s, size=%d]",
            owner,
            repository_name,
            path,
            size,
        )
        return unreadable
    if encoding is None or encoding == "none":
        # The API omits inlined content for empty files.
        if not raw_content and (not isinstance(size, int) or size == 0):
            return DiscoveredFile(path=path, present=True, sha=sha, content=b"")
        return unreadable
    if encoding != "base64" or not isinstance(raw_content, str):
        return unreadable
    stripped = "".join(raw_content.split())
    if len(stripped) > MAX_DECODED_BYTES * 4 // 3 + 4:
        return unreadable
    try:
        content = base64.b64decode(stripped, validate=True)
    except (binascii.Error, ValueError):
        return unreadable
    if len(content) > MAX_DECODED_BYTES:
        return unreadable
    return DiscoveredFile(path=path, present=True, sha=sha, content=content)


class GitHubContentsClient:
    """Minimal read-only client over the GitHub Contents + Repos APIs.

    Args:
        token_service: Service minting per-installation tokens. Defaults to
            a plain :class:`GitHubInstallationTokenService`.
        http_client: Optional ``httpx.Client``. Tests inject
            ``httpx.Client(transport=httpx.MockTransport(...))``.
    """

    def __init__(
        self,
        *,
        token_service: GitHubInstallationTokenService | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._token_service = token_service or GitHubInstallationTokenService()
        self._http_client = http_client

    def get_repository(self, *, owner: str, repository_name: str, installation_id: int) -> GitHubRepoMetadata:
        """Fetch repository metadata, resolving the actual default branch."""
        config = load_github_app_config()
        token = self._token_service.get_installation_token(installation_id)
        url = f"{config.api_base_url.rstrip('/')}/repos/{owner}/{repository_name}"
        response = self._get(url, token=token, timeout=config.timeout_seconds)
        _raise_for_status(response, owner=owner, repository_name=repository_name, what="metadata")
        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "github_client: unreadable metadata [owner=%s, repo=%s]",
                owner,
                repository_name,
            )
            raise ItqanError(
                "github_malformed_response",
                "GitHub returned an unreadable repository response.",
                502,
            ) from None
        if not isinstance(payload, dict):
            raise ItqanError(
                "github_malformed_response",
                "GitHub returned an unexpected repository response.",
                502,
            )
        default_branch = payload.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch.strip():
            logger.warning(
                "github_client: metadata without default branch [owner=%s, repo=%s]",
                owner,
                repository_name,
            )
            raise ItqanError(
                "github_malformed_response",
                "GitHub repository response is missing the default branch.",
                502,
            )
        return GitHubRepoMetadata(
            owner=owner,
            repository_name=repository_name,
            default_branch=default_branch,
        )

    def get_file(
        self,
        *,
        owner: str,
        repository_name: str,
        installation_id: int,
        path: str,
        ref: str,
    ) -> DiscoveredFile:
        """Fetch one root manifest file. 404 yields ``present=False``."""
        if path not in ALLOWED_MANIFEST_PATHS:
            raise ItqanError(
                "github_unsupported_manifest_path",
                "Only the V1 root manifest paths may be fetched.",
                500,
            )
        config = load_github_app_config()
        token = self._token_service.get_installation_token(installation_id)
        url = f"{config.api_base_url.rstrip('/')}/repos/{owner}/{repository_name}/contents/{path}"
        response = self._get(url, token=token, timeout=config.timeout_seconds, params={"ref": ref})
        if response.status_code == 404:
            logger.info(
                "github_client: file absent [owner=%s, repo=%s, path=%s, ref=%s]",
                owner,
                repository_name,
                path,
                ref,
            )
            return DiscoveredFile(path=path, present=False, sha=None, content=None)
        _raise_for_status(response, owner=owner, repository_name=repository_name, what=f"file:{path}")
        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "github_client: unreadable file response [owner=%s, repo=%s, path=%s]",
                owner,
                repository_name,
                path,
            )
            raise ItqanError(
                "github_malformed_response",
                "GitHub returned an unreadable file response.",
                502,
            ) from None
        return _decode_contents_payload(payload, owner=owner, repository_name=repository_name, path=path)

    def _get(
        self,
        url: str,
        *,
        token: str,
        timeout: float,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": GITHUB_USER_AGENT,
        }
        try:
            if self._http_client is not None:
                return self._http_client.get(url, headers=headers, params=params, timeout=timeout)
            with httpx.Client(timeout=timeout) as client:
                return client.get(url, headers=headers, params=params)
        except httpx.TimeoutException:
            raise ItqanError(
                "github_upstream_error",
                "GitHub request timed out.",
                502,
            ) from None
        except httpx.HTTPError as exc:
            logger.warning("github_client: network error [error_type=%s]", type(exc).__name__)
            raise ItqanError(
                "github_upstream_error",
                "GitHub request failed due to a network error.",
                502,
            ) from None

    def get_installation_state(self, *, installation_id: int) -> str | None:
        """Check current installation state via App JWT.

        Returns ``"active"`` if the installation exists and is not suspended,
        ``"suspended"`` if currently suspended, or ``None`` if the
        installation no longer exists. Never raises for 401/403 (maps to
        ``None`` — treat as not found).
        """
        config = load_github_app_config()
        app_jwt = create_github_app_jwt(app_id=config.app_id, private_key_pem=config.private_key_pem)
        url = f"{config.api_base_url.rstrip('/')}/app/installations/{installation_id}"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": GITHUB_USER_AGENT,
        }
        try:
            if self._http_client is not None:
                response = self._http_client.get(url, headers=headers, timeout=config.timeout_seconds)
            else:
                with httpx.Client(timeout=config.timeout_seconds) as client:
                    response = client.get(url, headers=headers)
        except httpx.TimeoutException:
            raise ItqanError(
                "github_upstream_error",
                "GitHub request timed out.",
                502,
            ) from None
        except httpx.HTTPError as exc:
            logger.warning("github_client: network error [error_type=%s]", type(exc).__name__)
            raise ItqanError(
                "github_upstream_error",
                "GitHub request failed due to a network error.",
                502,
            ) from None
        if response.status_code in (401, 403, 404):
            return None
        if response.status_code != 200:
            raise ItqanError(
                "github_upstream_error",
                f"GitHub request failed (status {response.status_code}).",
                502,
            )
        try:
            payload = response.json()
        except ValueError:
            raise ItqanError(
                "github_malformed_response",
                "GitHub returned an unreadable installation response.",
                502,
            ) from None
        if not isinstance(payload, dict):
            raise ItqanError(
                "github_malformed_response",
                "GitHub returned an unexpected installation response.",
                502,
            )
        suspended_by = payload.get("suspended_by")
        if suspended_by is not None:
            return "suspended"
        return "active"

    def is_repository_accessible(self, *, owner: str, repository_name: str, installation_id: int) -> bool:
        """Check whether the installation currently has access to the repository.

        Uses the installation token to query repository metadata. Returns
        ``True`` if the repository exists and is accessible, ``False`` if
        404/403 (inaccessible), ``True`` on other errors (conservative —
        allow the webhook through rather than blocking a legitimate event).
        """
        config = load_github_app_config()
        token = self._token_service.get_installation_token(installation_id)
        url = f"{config.api_base_url.rstrip('/')}/repos/{owner}/{repository_name}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": GITHUB_USER_AGENT,
        }
        try:
            if self._http_client is not None:
                response = self._http_client.get(url, headers=headers, timeout=config.timeout_seconds)
            else:
                with httpx.Client(timeout=config.timeout_seconds) as client:
                    response = client.get(url, headers=headers)
        except (httpx.TimeoutException, httpx.HTTPError):
            # On network errors, conservatively allow the event through —
            # stale events are harmless (they would just re-opt-in a repo
            # that's already opted in, which is idempotent).
            logger.warning(
                "github_client: network error checking repo accessibility [owner=%s, repo=%s]",
                owner,
                repository_name,
            )
            return True
        if response.status_code in (403, 404):
            return False
        if response.status_code != 200:
            # On unexpected errors, fail closed: do not grant access when
            # current state cannot be verified.
            logger.warning(
                "github_client: unexpected status checking repo accessibility [owner=%s, repo=%s, status=%d]",
                owner,
                repository_name,
                response.status_code,
            )
            raise ItqanError(
                "github_upstream_error",
                f"GitHub repository check failed (status {response.status_code}).",
                502,
            )
        return True
