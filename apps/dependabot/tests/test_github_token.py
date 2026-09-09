"""Unit tests for ``apps.dependabot.services.github_token``.

The HTTP layer is fully mocked with ``httpx.MockTransport`` (part of httpx
itself — no extra test library): zero live GitHub calls are made. Settings
are supplied with Django ``override_settings``; time is controlled with an
injected manual clock; the process-local token cache is cleared around every
test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import SimpleTestCase, override_settings
import httpx
import jwt
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.services.github_token import (
    GITHUB_ACCEPT_HEADER,
    GITHUB_API_VERSION,
    GITHUB_USER_AGENT,
    GitHubInstallationTokenService,
    clear_installation_token_cache,
)

APP_ID = 12345
INSTALLATION_ID = 987654
SKEW_SECONDS = 60
T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """Generate one RSA-2048 keypair and return (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


@pytest.fixture(autouse=True)
def _clean_token_cache():
    clear_installation_token_cache()
    yield
    clear_installation_token_cache()


class ManualClock:
    """Injectable clock for cache-expiry tests."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _valid_settings(private_pem: str, **overrides):
    values = {
        "ENABLE_ITQAN_DEPENDABOT": True,
        "GITHUB_APP_ID": APP_ID,
        "GITHUB_APP_PRIVATE_KEY": private_pem,
        "GITHUB_API_BASE_URL": "https://api.github.com",
        "GITHUB_HTTP_TIMEOUT_SECONDS": 10,
        "GITHUB_TOKEN_CACHE_SKEW_SECONDS": SKEW_SECONDS,
    }
    values.update(overrides)
    return override_settings(**values)


def _token_response(token: str, expires_at: datetime) -> httpx.Response:
    return httpx.Response(
        201,
        json={"token": token, "expires_at": expires_at.isoformat()},
    )


def _service(handler, clock: ManualClock, **client_kwargs) -> GitHubInstallationTokenService:
    return GitHubInstallationTokenService(
        http_client=httpx.Client(transport=httpx.MockTransport(handler), **client_kwargs),
        clock=clock,
    )


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# --- Happy path ---


def test_exchange_where_valid_returns_token(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)

    def handler(request: httpx.Request) -> httpx.Response:
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        token = _service(handler, clock).get_installation_token(INSTALLATION_ID)
    assert token == "ghs_test_token"


def test_exchange_where_called_sends_correct_endpoint_and_headers(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    clock = ManualClock(T0)
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.read().decode("utf-8")
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        _service(handler, clock).get_installation_token(INSTALLATION_ID)

    assert seen["method"] == "POST"
    assert seen["url"] == f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"
    assert seen["body"] == "{}"
    assert seen["headers"]["accept"] == GITHUB_ACCEPT_HEADER
    assert seen["headers"]["x-github-api-version"] == GITHUB_API_VERSION
    assert "itqan" in seen["headers"]["user-agent"].lower()
    assert seen["headers"]["user-agent"] == GITHUB_USER_AGENT

    authorization = seen["headers"]["authorization"]
    assert authorization.startswith("Bearer ")
    app_jwt = authorization.removeprefix("Bearer ")
    assert app_jwt.strip() != ""
    claims = jwt.decode(app_jwt, public_pem, algorithms=["RS256"], options={"verify_exp": False})
    assert claims["iss"] == str(APP_ID)
    assert claims["iat"] == int(T0.timestamp())
    assert claims["exp"] == int(T0.timestamp()) + 600


# --- Cache behavior ---


def test_exchange_where_token_cached_second_call_makes_no_request(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _token_response("ghs_cached", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        service = _service(handler, clock)
        assert service.get_installation_token(INSTALLATION_ID) == "ghs_cached"
        assert service.get_installation_token(INSTALLATION_ID) == "ghs_cached"
    assert len(calls) == 1


def test_exchange_where_cache_valid_before_skew_reuses_token(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _token_response("ghs_cached", T0 + timedelta(seconds=120))

    with _valid_settings(private_pem):
        service = _service(handler, clock)
        service.get_installation_token(INSTALLATION_ID)
        clock.now = T0 + timedelta(seconds=59)
        assert service.get_installation_token(INSTALLATION_ID) == "ghs_cached"
    assert len(calls) == 1


def test_exchange_where_skew_elapsed_refreshes_token(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _token_response(f"ghs_token_{len(calls)}", T0 + timedelta(seconds=120))

    with _valid_settings(private_pem):
        service = _service(handler, clock)
        assert service.get_installation_token(INSTALLATION_ID) == "ghs_token_1"
        clock.now = T0 + timedelta(seconds=61)
        assert service.get_installation_token(INSTALLATION_ID) == "ghs_token_2"
    assert len(calls) == 2


def test_exchange_where_tokens_cached_per_installation(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _token_response(f"ghs_for_{request.url.path.split('/')[-2]}", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        service = _service(handler, clock)
        first = service.get_installation_token(111)
        second = service.get_installation_token(222)
        assert first != second
        assert service.get_installation_token(111) == first
    assert len(calls) == 2


# --- Input validation (must fail before any HTTP request) ---


@pytest.mark.parametrize("bad_id", [0, -1, True, False, "123", None, 12.5])
def test_exchange_where_installation_id_invalid_raises_before_request(rsa_keypair, bad_id):
    private_pem, _ = rsa_keypair
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(request)
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(bad_id)
    assert exc_info.value.error_name == "github_invalid_installation_id"
    assert exc_info.value.status_code == 500
    assert calls == []


def test_exchange_where_flag_disabled_raises_without_request(rsa_keypair):
    private_pem, _ = rsa_keypair
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(request)
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings(private_pem, ENABLE_ITQAN_DEPENDABOT=False):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_dependabot_disabled"
    assert exc_info.value.status_code == 503
    assert calls == []


@pytest.mark.parametrize(
    "setting_overrides",
    [
        {"GITHUB_APP_ID": 0},
        {"GITHUB_APP_ID": -3},
        {"GITHUB_APP_ID": True},
        {"GITHUB_APP_ID": "123"},
        {"GITHUB_APP_PRIVATE_KEY": ""},
        {"GITHUB_APP_PRIVATE_KEY": "   "},
        {"GITHUB_API_BASE_URL": "not-a-url"},
        {"GITHUB_API_BASE_URL": "http://insecure.example.com"},
        {"GITHUB_API_BASE_URL": ""},
        {"GITHUB_HTTP_TIMEOUT_SECONDS": 0},
        {"GITHUB_HTTP_TIMEOUT_SECONDS": -5},
        {"GITHUB_HTTP_TIMEOUT_SECONDS": "ten"},
        {"GITHUB_TOKEN_CACHE_SKEW_SECONDS": -1},
        {"GITHUB_TOKEN_CACHE_SKEW_SECONDS": True},
    ],
)
def test_exchange_where_settings_invalid_raises_misconfigured_without_request(rsa_keypair, setting_overrides):
    private_pem, _ = rsa_keypair
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(request)
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings(private_pem, **setting_overrides):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_app_misconfigured"
    assert exc_info.value.status_code == 500
    assert calls == []


def test_exchange_where_private_key_malformed_raises_misconfigured(rsa_keypair):
    _, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
        calls.append(request)
        return _token_response("ghs_test_token", T0 + timedelta(hours=1))

    with _valid_settings("not a pem at all"):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, clock).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_app_misconfigured"
    assert calls == []


# --- GitHub error responses ---


def test_exchange_where_github_401_raises_exchange_failed(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_token_exchange_failed"
    assert exc_info.value.status_code == 502


def test_exchange_where_github_403_without_rate_limit_raises_exchange_failed(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Resource not accessible by integration"})

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_token_exchange_failed"
    assert exc_info.value.status_code == 502


def test_exchange_where_github_500_raises_exchange_failed(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "Internal Server Error"})

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_token_exchange_failed"
    assert exc_info.value.status_code == 502


def test_exchange_where_github_429_raises_rate_limited_with_retry_after(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "120"}, json={"message": "API rate limit exceeded"})

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_rate_limited"
    assert exc_info.value.status_code == 503
    assert exc_info.value.extra == {"retry_after_seconds": 120}


def test_exchange_where_github_403_with_rate_limit_remaining_zero_raises_rate_limited(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0"},
            json={"message": "API rate limit exceeded for installation."},
        )

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_rate_limited"
    assert exc_info.value.status_code == 503


def test_exchange_where_github_403_with_secondary_rate_limit_message_raises_rate_limited(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "You have exceeded a secondary rate limit."})

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_rate_limited"


def test_exchange_where_timeout_raises_exchange_failed(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_token_exchange_failed"
    assert exc_info.value.status_code == 502


def test_exchange_where_network_error_raises_exchange_failed(rsa_keypair):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_token_exchange_failed"
    assert exc_info.value.status_code == 502


# --- Malformed GitHub responses ---


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(201, content=b"this is not json"),
        httpx.Response(201, json={"expires_at": _iso(T0 + timedelta(hours=1))}),
        httpx.Response(201, json={"token": "", "expires_at": _iso(T0 + timedelta(hours=1))}),
        httpx.Response(201, json={"token": 12345, "expires_at": _iso(T0 + timedelta(hours=1))}),
        httpx.Response(201, json={"token": "ghs_test_token"}),
        httpx.Response(201, json={"token": "ghs_test_token", "expires_at": "not-a-date"}),
        httpx.Response(201, json={"token": "ghs_test_token", "expires_at": 12345}),
        httpx.Response(201, json={"token": "ghs_test_token", "expires_at": "2026-09-06T12:00:00"}),
        httpx.Response(201, json=["ghs_test_token"]),
    ],
    ids=[
        "non-json-body",
        "missing-token",
        "empty-token",
        "non-string-token",
        "missing-expires-at",
        "garbage-expires-at",
        "non-string-expires-at",
        "naive-expires-at",
        "non-object-body",
    ],
)
def test_exchange_where_response_malformed_raises_malformed_response(rsa_keypair, response):
    private_pem, _ = rsa_keypair

    def handler(request: httpx.Request) -> httpx.Response:
        return response

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError) as exc_info:
            _service(handler, ManualClock(T0)).get_installation_token(INSTALLATION_ID)
    assert exc_info.value.error_name == "github_malformed_response"
    assert exc_info.value.status_code == 502


def test_exchange_where_failed_exchange_does_not_populate_cache(rsa_keypair):
    private_pem, _ = rsa_keypair
    clock = ManualClock(T0)
    calls = []

    def failing(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"message": "boom"})

    def succeeding(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return _token_response("ghs_recovered", T0 + timedelta(hours=1))

    with _valid_settings(private_pem):
        with pytest.raises(ItqanError):
            _service(failing, clock).get_installation_token(INSTALLATION_ID)
        assert _service(succeeding, clock).get_installation_token(INSTALLATION_ID) == "ghs_recovered"
    assert len(calls) == 2


# --- Secret-handling security tests (need SimpleTestCase for assertLogs) ---


class InstallationTokenSecrecyTest(SimpleTestCase):
    """No private key, App JWT, or installation token may leak."""

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

    def _settings(self, **overrides):
        values = {
            "ENABLE_ITQAN_DEPENDABOT": True,
            "GITHUB_APP_ID": APP_ID,
            "GITHUB_APP_PRIVATE_KEY": self.private_pem,
            "GITHUB_API_BASE_URL": "https://api.github.com",
            "GITHUB_HTTP_TIMEOUT_SECONDS": 10,
            "GITHUB_TOKEN_CACHE_SKEW_SECONDS": SKEW_SECONDS,
        }
        values.update(overrides)
        return override_settings(**values)

    def test_exchange_does_not_log_token_or_jwt(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers["authorization"]
            return _token_response("ghs_CANARY_TOKEN", T0 + timedelta(hours=1))

        service = GitHubInstallationTokenService(
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            clock=ManualClock(T0),
        )
        with self._settings():
            with self.assertLogs("apps.dependabot.services.github_token", level=logging.DEBUG) as cm:
                token = service.get_installation_token(INSTALLATION_ID)
        app_jwt = seen["authorization"].removeprefix("Bearer ")
        messages = " ".join(record.getMessage() for record in cm.records)
        assert token == "ghs_CANARY_TOKEN"
        assert "ghs_CANARY_TOKEN" not in messages
        assert app_jwt not in messages
        assert "Bearer ghs_CANARY_TOKEN" not in messages

    def test_exchange_failure_does_not_echo_canary_token_in_exception(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                201,
                json={"token": "ghs_CANARY_BAD_TOKEN", "expires_at": "not-a-date"},
            )

        service = GitHubInstallationTokenService(
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            clock=ManualClock(T0),
        )
        with self._settings():
            with self.assertRaises(ItqanError) as ctx:
                service.get_installation_token(INSTALLATION_ID)
        assert ctx.exception.error_name == "github_malformed_response"
        assert "ghs_CANARY_BAD_TOKEN" not in ctx.exception.message
        assert "ghs_CANARY_BAD_TOKEN" not in str(ctx.exception.extra)

    def test_exchange_does_not_leak_private_key_on_signing_failure(self):
        marker = "CANARY-PRIVATE-KEY-MATERIAL"
        bad_pem = (
            "-----BEGIN PRIVATE KEY-----\n"
            f"{marker}\n"
            "AAAAAAAAAAAAA_invalid_base64_BBBBBBBBBBBB\n"
            "-----END PRIVATE KEY-----\n"
        )

        def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must not run
            return _token_response("ghs_test_token", T0 + timedelta(hours=1))  # pragma: no cover

        service = GitHubInstallationTokenService(
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            clock=ManualClock(T0),
        )
        with self._settings(GITHUB_APP_PRIVATE_KEY=bad_pem):
            # The signing failure is logged by the JWT module (same logger
            # convention as the github_jwt secrecy tests).
            with self.assertLogs("apps.dependabot.services.github_jwt", level=logging.DEBUG) as cm:
                with self.assertRaises(ItqanError) as ctx:
                    service.get_installation_token(INSTALLATION_ID)
        assert ctx.exception.error_name == "github_app_misconfigured"
        assert marker not in ctx.exception.message
        assert marker not in str(ctx.exception.extra)
        for record in cm.records:
            assert marker not in record.getMessage()

    def test_exchange_network_failure_does_not_log_authorization_header(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers["authorization"]
            raise httpx.ConnectError("connection refused")

        service = GitHubInstallationTokenService(
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            clock=ManualClock(T0),
        )
        with self._settings():
            with self.assertLogs("apps.dependabot.services.github_token", level=logging.DEBUG) as cm:
                with self.assertRaises(ItqanError) as ctx:
                    service.get_installation_token(INSTALLATION_ID)
        assert ctx.exception.error_name == "github_token_exchange_failed"
        app_jwt = seen["authorization"].removeprefix("Bearer ")
        assert "Bearer " not in ctx.exception.message
        assert app_jwt not in ctx.exception.message
        assert app_jwt not in str(ctx.exception.extra)
        for record in cm.records:
            assert app_jwt not in record.getMessage()
            assert "Bearer " not in record.getMessage()
