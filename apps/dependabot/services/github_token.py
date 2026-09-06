"""GitHub App installation-token exchange for the Itqan Dependabot updater.

Two different tokens are involved in GitHub App authentication:

- The **App JWT** (see ``apps.dependabot.services.github_jwt``) proves the
  identity of the GitHub App itself. It is short-lived (10 minutes max),
  minted locally from the App ID + RSA private key, and can only be used
  for a handful of App-level endpoints — it cannot read repository content.
- The **installation token** is obtained by exchanging the App JWT at
  ``POST /app/installations/{installation_id}/access_tokens``. It acts on
  behalf of one specific installation (i.e. the set of repositories that
  installed the App), expires after ~1 hour, and carries only the
  permissions the installation was granted. All repository access in later
  phases (manifest discovery, PR automation) uses installation tokens, so a
  leaked token is confined to one installation and expires quickly.

Security rules:

- The private key, the App JWT, and installation tokens never appear in any
  exception message, ``extra`` payload, or log line. Logs carry only the
  installation ID, HTTP status codes, and expiry timestamps.
- Tokens live only in a process-local in-memory cache. They are never
  written to the database, to disk, or to any shared cache.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import math
from threading import Lock

from django.conf import settings as django_settings
import httpx

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.services.github_jwt import create_github_app_jwt

logger = logging.getLogger(__name__)

GITHUB_ACCEPT_HEADER = "application/vnd.github+json"
GITHUB_API_VERSION = "2022-11-28"
GITHUB_USER_AGENT = "itqan-dependabot"


@dataclass(frozen=True)
class GitHubAppConfig:
    """Resolved Dependabot GitHub App settings. Built lazily per call."""

    enabled: bool
    app_id: int
    private_key_pem: str
    api_base_url: str
    timeout_seconds: float
    cache_skew_seconds: int


def load_github_app_config() -> GitHubAppConfig:
    """Read the Dependabot GitHub App settings without validating secrets.

    No signing or network activity happens here; invalid values are reported
    lazily by :class:`GitHubInstallationTokenService` as ``ItqanError``.
    """
    return GitHubAppConfig(
        enabled=bool(getattr(django_settings, "ENABLE_ITQAN_DEPENDABOT", False)),
        app_id=getattr(django_settings, "GITHUB_APP_ID", 0),
        private_key_pem=getattr(django_settings, "GITHUB_APP_PRIVATE_KEY", "") or "",
        api_base_url=getattr(django_settings, "GITHUB_API_BASE_URL", "https://api.github.com") or "",
        timeout_seconds=getattr(django_settings, "GITHUB_HTTP_TIMEOUT_SECONDS", 10),
        cache_skew_seconds=getattr(django_settings, "GITHUB_TOKEN_CACHE_SKEW_SECONDS", 60),
    )


@dataclass
class _CachedInstallationToken:
    token: str
    expires_at: datetime


_token_cache: dict[int, _CachedInstallationToken] = {}
_token_cache_lock = Lock()


def clear_installation_token_cache() -> None:
    """Drop all cached installation tokens.

    Operational hook for credential rotation, also used to isolate tests.
    """
    with _token_cache_lock:
        _token_cache.clear()


def _get_cached_token(installation_id: int) -> _CachedInstallationToken | None:
    with _token_cache_lock:
        return _token_cache.get(installation_id)


def _store_cached_token(installation_id: int, token: str, expires_at: datetime) -> None:
    with _token_cache_lock:
        _token_cache[installation_id] = _CachedInstallationToken(token=token, expires_at=expires_at)


def _validate_installation_id(installation_id: int) -> None:
    if not isinstance(installation_id, int) or isinstance(installation_id, bool) or installation_id <= 0:
        raise ItqanError(
            "github_invalid_installation_id",
            "GitHub installation ID must be a positive integer.",
            500,
        )


def _validate_config(config: GitHubAppConfig) -> None:
    if (
        not isinstance(config.app_id, int)
        or isinstance(config.app_id, bool)
        or config.app_id <= 0
        or not isinstance(config.private_key_pem, str)
        or not config.private_key_pem.strip()
    ):
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub App ID and private key must be configured.",
            500,
        )
    if not isinstance(config.api_base_url, str) or not config.api_base_url.startswith("https://"):
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub API base URL must be an https:// URL.",
            500,
        )
    if (
        not isinstance(config.timeout_seconds, (int, float))
        or isinstance(config.timeout_seconds, bool)
        or not math.isfinite(config.timeout_seconds)
        or config.timeout_seconds <= 0
    ):
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub HTTP timeout must be a positive number of seconds.",
            500,
        )
    if (
        not isinstance(config.cache_skew_seconds, int)
        or isinstance(config.cache_skew_seconds, bool)
        or config.cache_skew_seconds < 0
    ):
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub token cache skew must be a non-negative integer.",
            500,
        )


def _parse_expires_at(raw: object) -> datetime | None:
    """Parse GitHub's ``expires_at`` (e.g. ``2026-09-06T16:00:00Z``)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text[-1:] in ("Z", "z") else text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _is_rate_limited(response: httpx.Response) -> bool:
    """Decide whether a 403/429 response signals rate limiting.

    Only boolean signals are inspected; the response body is never surfaced.
    """
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


def _parse_token_response(response: httpx.Response, installation_id: int) -> tuple[str, datetime]:
    if _is_rate_limited(response):
        retry_after = response.headers.get("retry-after")
        extra: dict[str, int] = {}
        if retry_after is not None and retry_after.isdigit():
            extra["retry_after_seconds"] = int(retry_after)
        logger.warning(
            "github_token: rate limited [installation_id=%d, status=%d]",
            installation_id,
            response.status_code,
        )
        raise ItqanError(
            "github_rate_limited",
            "GitHub API rate limit exceeded.",
            503,
            extra=extra,
        )
    if response.status_code == 401:
        logger.warning("github_token: exchange rejected credentials [installation_id=%d]", installation_id)
        raise ItqanError(
            "github_token_exchange_failed",
            "GitHub rejected the App credentials.",
            502,
        )
    if response.status_code != 201:
        logger.warning(
            "github_token: exchange failed [installation_id=%d, status=%d]",
            installation_id,
            response.status_code,
        )
        raise ItqanError(
            "github_token_exchange_failed",
            f"GitHub token exchange failed (status {response.status_code}).",
            502,
        )
    try:
        payload = response.json()
    except ValueError:
        logger.warning("github_token: unreadable response [installation_id=%d]", installation_id)
        raise ItqanError(
            "github_malformed_response",
            "GitHub returned an unreadable token response.",
            502,
        ) from None
    if not isinstance(payload, dict):
        logger.warning("github_token: unexpected response shape [installation_id=%d]", installation_id)
        raise ItqanError(
            "github_malformed_response",
            "GitHub returned an unexpected token response.",
            502,
        )
    token = payload.get("token")
    expires_at = _parse_expires_at(payload.get("expires_at"))
    if not isinstance(token, str) or not token or expires_at is None:
        logger.warning("github_token: incomplete response [installation_id=%d]", installation_id)
        raise ItqanError(
            "github_malformed_response",
            "GitHub token response is missing the token or its expiry.",
            502,
        )
    return token, expires_at


class GitHubInstallationTokenService:
    """Mint App JWTs and exchange them for per-installation access tokens.

    Args:
        http_client: Optional ``httpx.Client``. When omitted, a short-lived
            client with the configured timeout is created per exchange.
            Tests inject ``httpx.Client(transport=httpx.MockTransport(...))``
            so no live GitHub call is ever made.
        clock: Optional zero-argument callable returning the current
            timezone-aware UTC ``datetime``. Defaults to the wall clock;
            tests inject a manual clock to control cache expiry.
    """

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._http_client = http_client
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(tz=UTC))

    def get_installation_token(self, installation_id: int) -> str:
        """Return a valid installation token, reusing or refreshing the cache.

        Raises:
            ItqanError: ``github_invalid_installation_id`` (bad input),
                ``github_dependabot_disabled`` (flag off),
                ``github_app_misconfigured`` (bad local settings),
                ``github_token_exchange_failed`` (auth/network/server error),
                ``github_rate_limited`` (429 / rate-limit 403),
                ``github_malformed_response`` (unparseable GitHub reply).
                Secrets never appear in the message or ``extra``.
        """
        _validate_installation_id(installation_id)
        config = load_github_app_config()
        if not config.enabled:
            raise ItqanError(
                "github_dependabot_disabled",
                "Itqan Dependabot updater is disabled.",
                503,
            )
        _validate_config(config)

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=UTC)

        cached = _get_cached_token(installation_id)
        if cached is not None and now < cached.expires_at - timedelta(seconds=config.cache_skew_seconds):
            logger.info("github_token: reused cached token [installation_id=%d]", installation_id)
            return cached.token

        app_jwt = create_github_app_jwt(app_id=config.app_id, private_key_pem=config.private_key_pem, now=now)
        token, expires_at = self._exchange(config, installation_id, app_jwt)
        _store_cached_token(installation_id, token, expires_at)
        logger.info(
            "github_token: issued installation token [installation_id=%d, expires_at=%s]",
            installation_id,
            expires_at.isoformat(),
        )
        return token

    def _exchange(self, config: GitHubAppConfig, installation_id: int, app_jwt: str) -> tuple[str, datetime]:
        url = f"{config.api_base_url.rstrip('/')}/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": GITHUB_ACCEPT_HEADER,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": GITHUB_USER_AGENT,
        }
        try:
            if self._http_client is not None:
                response = self._http_client.post(url, headers=headers, json={}, timeout=config.timeout_seconds)
            else:
                with httpx.Client(timeout=config.timeout_seconds) as client:
                    response = client.post(url, headers=headers, json={})
        except httpx.TimeoutException:
            logger.warning("github_token: exchange timed out [installation_id=%d]", installation_id)
            raise ItqanError(
                "github_token_exchange_failed",
                "GitHub token exchange timed out.",
                502,
            ) from None
        except httpx.HTTPError as exc:
            logger.warning(
                "github_token: exchange network error [installation_id=%d, error_type=%s]",
                installation_id,
                type(exc).__name__,
            )
            raise ItqanError(
                "github_token_exchange_failed",
                "GitHub token exchange failed due to a network error.",
                502,
            ) from None
        return _parse_token_response(response, installation_id)
