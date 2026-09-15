"""Tests for manifest discovery orchestration.

End-to-end through the real token service, watched service, and database,
with GitHub fully mocked (one ``httpx.MockTransport`` routing the token
exchange, metadata, and contents endpoints by path). Zero live calls.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings
import httpx

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.models import WatchedRepository
from apps.dependabot.services.github_client import LOCKFILE_PATH, MANIFEST_PATH
from apps.dependabot.services.github_token import clear_installation_token_cache
from apps.dependabot.services.manifest_discovery import ManifestDiscoveryService
from apps.dependabot.services.watched_repositories import WatchedRepositoryService

HOST = "github"
OWNER = "itqan-community"
REPO = "sample-app"
APP_ID = 12345
INSTALLATION_ID = 777
T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)
FAR_FUTURE = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)
MANIFEST_SHA = "a" * 40
LOCKFILE_SHA = "b" * 40
CANARY_TOKEN = "ghs_CANARY_INSTALLATION_TOKEN"

FRESH_MANIFEST = 'schema_version: 1\n\nassets:\n  toolkit:\n    version: "^1.0.0"\n'
FRESH_LOCKFILE = 'lockfile_version: 1\nmanifest_schema_version: 1\n\nassets:\n  "toolkit":\n    constraint: "^1.0.0"\n    version: "1.2.4"\n'


class ManualClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _file_payload(text: str, sha: str, path: str) -> dict:
    return {
        "type": "file",
        "encoding": "base64",
        "size": len(text.encode("utf-8")),
        "name": path.rsplit("/", 1)[-1],
        "path": path,
        "sha": sha,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
    }


class GitHubDouble:
    """Routes mocked GitHub endpoints by path and records every request."""

    def __init__(
        self,
        *,
        metadata: dict | httpx.Response | Exception | None = None,
        manifest: str | httpx.Response | Exception | None = FRESH_MANIFEST,
        lockfile: str | httpx.Response | Exception | None = FRESH_LOCKFILE,
        token: str = "ghs_test_token",
    ) -> None:
        self.metadata = metadata if metadata is not None else {"default_branch": "develop"}
        self.manifest = manifest
        self.lockfile = lockfile
        self.token = token
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path, dict(request.url.params)))
        path = request.url.path
        if path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": self.token, "expires_at": FAR_FUTURE.isoformat()})
        if "/contents/" in path:
            if path.endswith(MANIFEST_PATH):
                return self._file_response(self.manifest, MANIFEST_SHA, MANIFEST_PATH)
            return self._file_response(self.lockfile, LOCKFILE_SHA, LOCKFILE_PATH)
        return self._metadata_response()

    def _metadata_response(self) -> httpx.Response:
        if isinstance(self.metadata, Exception):
            raise self.metadata
        if isinstance(self.metadata, httpx.Response):
            return self.metadata
        return httpx.Response(200, json=self.metadata)

    def _file_response(self, spec, sha: str, path: str) -> httpx.Response:
        if spec is None:
            return httpx.Response(404, json={"message": "Not Found"})
        if isinstance(spec, Exception):
            raise spec
        if isinstance(spec, httpx.Response):
            return spec
        return httpx.Response(200, json=_file_payload(spec, sha, path))


class ManifestDiscoveryTest(TestCase):
    private_pem: str

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")

    def setUp(self):
        super().setUp()
        clear_installation_token_cache()
        self.clock = ManualClock(T0)
        self.watched_service = WatchedRepositoryService()
        self.addCleanup(clear_installation_token_cache)

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_APP_ID": APP_ID,
            "GITHUB_APP_PRIVATE_KEY": self.private_pem,
            "GITHUB_API_BASE_URL": "https://api.github.com",
            "GITHUB_HTTP_TIMEOUT_SECONDS": 10,
            "GITHUB_TOKEN_CACHE_SKEW_SECONDS": 60,
        }
        values.update(overrides)
        return override_settings(**values)

    def _service(self, double: GitHubDouble) -> ManifestDiscoveryService:
        from apps.dependabot.services.github_client import GitHubContentsClient
        from apps.dependabot.services.github_token import GitHubInstallationTokenService

        transport = httpx.MockTransport(double)
        token_service = GitHubInstallationTokenService(http_client=httpx.Client(transport=transport))
        return ManifestDiscoveryService(
            contents_client=GitHubContentsClient(
                token_service=token_service,
                http_client=httpx.Client(transport=transport),
            ),
            watched_service=self.watched_service,
            clock=self.clock,
        )

    def _watch(self, **kwargs):
        values = {
            "host": HOST,
            "owner": OWNER,
            "repository_name": REPO,
            "installation_id": INSTALLATION_ID,
        }
        values.update(kwargs)
        return self.watched_service.opt_in(**values)

    def _row(self) -> WatchedRepository:
        return WatchedRepository.objects.get(host=HOST, owner=OWNER, repository_name=REPO)

    # --- Gates: zero GitHub calls on refusal ---

    def test_discover_where_flag_disabled_makes_no_calls(self):
        self._watch()
        double = GitHubDouble()
        with self._settings(ENABLE_ITQAN_DEPENDABOT=False):
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_dependabot_disabled"
        assert double.calls == []

    def test_discover_where_opted_out_makes_no_calls(self):
        self._watch()
        self.watched_service.opt_out(host=HOST, owner=OWNER, repository_name=REPO)
        double = GitHubDouble()
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "dependabot_repository_not_found"
        assert double.calls == []

    def test_discover_where_suspended_makes_no_calls(self):
        self._watch()
        self.watched_service.suspend(host=HOST, owner=OWNER, repository_name=REPO)
        double = GitHubDouble()
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "dependabot_repository_not_found"
        assert double.calls == []

    def test_discover_where_unknown_repo_makes_no_calls(self):
        double = GitHubDouble()
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner="ghost", repository_name="nothing")
        assert ctx.exception.error_name == "dependabot_repository_not_found"
        assert double.calls == []

    # --- Happy path ---

    def test_discover_where_fresh_resolves_branch_and_persists(self):
        self._watch()
        double = GitHubDouble()
        with self._settings():
            result = self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)

        assert result.state == "FRESH"
        assert result.default_branch == "develop"
        assert result.manifest_sha == MANIFEST_SHA
        assert result.lockfile_sha == LOCKFILE_SHA
        assert result.manifest is not None and result.lockfile is not None
        # Both file reads used the resolved branch, not the "main" guess.
        content_calls = [(method, path, params) for method, path, params in double.calls if "/contents/" in path]
        assert len(content_calls) == 2
        assert {params.get("ref") for _, _, params in content_calls} == {"develop"}

        row = self._row()
        assert row.default_branch == "develop"
        assert row.last_manifest_sha == MANIFEST_SHA
        assert row.last_lockfile_sha == LOCKFILE_SHA
        assert row.last_checked_at == T0
        assert row.status == WatchedRepository.StatusChoice.OPTED_IN

    def test_discover_where_missing_persists_null_lockfile(self):
        self._watch()
        double = GitHubDouble(lockfile=None)
        with self._settings():
            result = self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)

        assert result.state == "MISSING"
        assert result.lockfile_sha is None
        row = self._row()
        assert row.last_manifest_sha == MANIFEST_SHA
        assert row.last_lockfile_sha is None
        assert row.last_checked_at == T0

    def test_discover_where_absent_persists_nulls(self):
        self._watch()
        double = GitHubDouble(manifest=None, lockfile=None)
        with self._settings():
            result = self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert result.state == "ABSENT"
        row = self._row()
        assert (row.last_manifest_sha, row.last_lockfile_sha, row.last_checked_at) == (None, None, T0)

    def test_discover_where_invalid_manifest_persists_shas_without_status_change(self):
        self._watch()
        double = GitHubDouble(manifest="schema_version: true\nassets: {}\n")
        with self._settings():
            result = self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert result.state == "INVALID"
        row = self._row()
        assert row.last_manifest_sha == MANIFEST_SHA
        assert row.last_checked_at == T0
        assert row.status == WatchedRepository.StatusChoice.OPTED_IN

    # --- Failure paths persist nothing ---

    def test_discover_where_repository_404_persists_nothing(self):
        self._watch()
        double = GitHubDouble(metadata=httpx.Response(404, json={"message": "Not Found"}))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_repository_unavailable"
        row = self._row()
        assert (row.last_manifest_sha, row.last_lockfile_sha, row.last_checked_at) == (None, None, None)
        assert row.default_branch == "main"

    def test_discover_where_401_persists_nothing(self):
        self._watch()
        double = GitHubDouble(metadata=httpx.Response(401, json={"message": "Bad credentials"}))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_authentication_failed"
        assert self._row().last_checked_at is None

    def test_discover_where_permission_403_persists_nothing(self):
        self._watch()
        double = GitHubDouble(manifest=httpx.Response(403, json={"message": "Resource not accessible by integration"}))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_access_denied"
        assert self._row().last_checked_at is None

    def test_discover_where_rate_limited_persists_nothing(self):
        self._watch()
        double = GitHubDouble(manifest=httpx.Response(429, json={"message": "API rate limit exceeded"}))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_rate_limited"
        assert self._row().last_checked_at is None

    def test_discover_where_timeout_persists_nothing(self):
        self._watch()
        double = GitHubDouble(metadata=httpx.ConnectTimeout("timed out"))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_upstream_error"
        assert self._row().last_checked_at is None

    def test_discover_where_malformed_metadata_persists_nothing(self):
        self._watch()
        double = GitHubDouble(metadata={"full_name": f"{OWNER}/{REPO}"})
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_malformed_response"
        assert self._row().last_checked_at is None

    def test_discover_where_malformed_json_persists_nothing(self):
        self._watch()
        double = GitHubDouble(manifest=httpx.Response(200, content=b"not json"))
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert ctx.exception.error_name == "github_malformed_response"
        assert self._row().last_checked_at is None

    # --- Secrecy ---

    def test_discover_does_not_log_installation_token(self):
        self._watch()
        double = GitHubDouble(token=CANARY_TOKEN)
        with self._settings():
            # The token service logs issuance on this path; the contents
            # client stays silent on success — assert on the emitting logger.
            with self.assertLogs("apps.dependabot.services.github_token", level=logging.DEBUG) as token_logs:
                result = self._service(double).discover(host=HOST, owner=OWNER, repository_name=REPO)
        assert result.state == "FRESH"
        messages = " ".join(record.getMessage() for record in token_logs.records)
        assert CANARY_TOKEN not in messages
