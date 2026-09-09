"""Unit tests for ``apps.dependabot.services.github_jwt``.

Pure-function tests using ``SimpleTestCase`` (no database) and plain
``pytest`` functions for the parametrized cases. The only external
dependency is a single in-process generated RSA-2048 key reused across
the class.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import SimpleTestCase
from freezegun import freeze_time
import jwt
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.services.github_jwt import MAX_LIFETIME_SECONDS, create_github_app_jwt


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[str, str]:
    """Generate one RSA-2048 keypair and return (private_pem, public_pem)."""
    private_pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        .decode("ascii")
    )
    public_pem = (
        serialization.load_pem_private_key(private_pem.encode("ascii"), password=None)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    return private_pem, public_pem


def _decode(public_pem: str, token: str) -> dict:
    # ``verify_exp`` is disabled because the test freezes time in the
    # past relative to the runner's wall clock. RS256 signature
    # verification is still enforced via the public key.
    return jwt.decode(
        token,
        public_pem,
        algorithms=["RS256"],
        options={"verify_aud": False, "verify_exp": False},
    )


# --- Happy path ---


def test_issue_jwt_where_credentials_valid_claims_are_correct(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    fixed = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    expected_iat = int(fixed.timestamp())

    token = create_github_app_jwt(app_id=12345, private_key_pem=private_pem, now=fixed)

    claims = _decode(public_pem, token)
    assert claims["iss"] == "12345"
    assert isinstance(claims["iss"], str)
    assert claims["iat"] == expected_iat
    assert claims["exp"] == expected_iat + MAX_LIFETIME_SECONDS
    assert claims["exp"] - claims["iat"] == MAX_LIFETIME_SECONDS


def test_issue_jwt_where_freezegun_advances_time_claims_advance(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    first_now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    second_now = datetime(2026, 1, 1, 0, 5, 0, tzinfo=UTC)

    first = _decode(public_pem, create_github_app_jwt(app_id=1, private_key_pem=private_pem, now=first_now))
    second = _decode(public_pem, create_github_app_jwt(app_id=1, private_key_pem=private_pem, now=second_now))

    assert second["iat"] - first["iat"] == 300
    assert second["exp"] - first["exp"] == 300


def test_issue_jwt_where_now_omitted_uses_utc_wall_clock(rsa_keypair):
    private_pem, public_pem = rsa_keypair
    fixed = datetime(2026, 7, 4, 10, 0, 0, tzinfo=UTC)
    with freeze_time(fixed):
        token = create_github_app_jwt(app_id=1, private_key_pem=private_pem)
    claims = _decode(public_pem, token)
    assert claims["iat"] == int(fixed.timestamp())
    assert claims["exp"] == claims["iat"] + MAX_LIFETIME_SECONDS


# --- Configuration errors (parametrized) ---


@pytest.mark.parametrize("bad_app_id", [0, -1, True])
def test_issue_jwt_where_app_id_invalid_raises_misconfigured(rsa_keypair, bad_app_id):
    private_pem, _ = rsa_keypair
    with pytest.raises(ItqanError) as exc_info:
        create_github_app_jwt(
            app_id=bad_app_id,
            private_key_pem=private_pem,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert exc_info.value.error_name == "github_app_misconfigured"
    assert exc_info.value.status_code == 500
    assert exc_info.value.extra == {}


@pytest.mark.parametrize("bad_key", ["", "   \n\t  "])
def test_issue_jwt_where_private_key_empty_raises_misconfigured(rsa_keypair, bad_key):
    _, _ = rsa_keypair
    with pytest.raises(ItqanError) as exc_info:
        create_github_app_jwt(
            app_id=1,
            private_key_pem=bad_key,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert exc_info.value.error_name == "github_app_misconfigured"
    assert exc_info.value.extra == {}


@pytest.mark.parametrize(
    "bad_pem",
    [
        "not a pem at all",  # non-PEM string
        (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "CANARY-MALFORMED-PEM\n"
            "not_base64_at_all\n"
            "-----END RSA PRIVATE KEY-----\n"
        ),
    ],
)
def test_issue_jwt_where_private_key_malformed_raises_misconfigured_without_echo(bad_pem):
    with pytest.raises(ItqanError) as exc_info:
        create_github_app_jwt(
            app_id=1,
            private_key_pem=bad_pem,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )
    assert exc_info.value.error_name == "github_app_misconfigured"
    assert exc_info.value.extra == {}
    # The bad-PEM body must never be echoed into the exception.
    assert "CANARY-MALFORMED-PEM" not in exc_info.value.message
    assert "not_base64_at_all" not in exc_info.value.message


@pytest.mark.parametrize(
    "bad_now",
    [
        datetime(2026, 1, 1, 0, 0, 0),  # naive
        "2026-01-01",  # not a datetime
        0,  # not a datetime
    ],
)
def test_issue_jwt_where_now_invalid_raises_misconfigured(rsa_keypair, bad_now):
    private_pem, _ = rsa_keypair
    with pytest.raises(ItqanError) as exc_info:
        create_github_app_jwt(app_id=1, private_key_pem=private_pem, now=bad_now)
    assert exc_info.value.error_name == "github_app_misconfigured"


# --- Secret-handling security tests (need SimpleTestCase for assertLogs) ---


class CreateGithubAppJwtSecurityTest(SimpleTestCase):
    """Security tests that use ``assertLogs`` to assert on log content."""

    private_key_pem: str

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.private_key_pem = (
            rsa.generate_private_key(public_exponent=65537, key_size=2048)
            .private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            .decode("ascii")
        )

    def test_issue_jwt_does_not_log_token(self):
        with self.assertLogs("apps.dependabot.services.github_jwt", level=logging.INFO) as cm:
            token = create_github_app_jwt(
                app_id=1,
                private_key_pem=self.private_key_pem,
                now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            )
        for record in cm.records:
            self.assertNotIn(token, record.getMessage())

    def test_issue_jwt_does_not_leak_private_key_in_exception_on_signing_failure(self):
        marker = "CANARY-MARKER-DO-NOT-LEAK"
        corrupted_pem = (
            "-----BEGIN PRIVATE KEY-----\n"
            f"{marker}\n"
            "AAAAAAAAAAAAA_invalid_base64_BBBBBBBBBBBB\n"
            "-----END PRIVATE KEY-----\n"
        )
        with self.assertRaises(ItqanError) as ctx:
            create_github_app_jwt(
                app_id=1,
                private_key_pem=corrupted_pem,
                now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
            )
        self.assertEqual("github_app_misconfigured", ctx.exception.error_name)
        self.assertNotIn(marker, ctx.exception.message)
        self.assertNotIn(marker, str(ctx.exception.extra))

    def test_issue_jwt_does_not_log_private_key_on_signing_failure(self):
        marker = "CANARY-PRIVATE-KEY-LOG"
        bad_pem = "-----BEGIN RSA PRIVATE KEY-----\n" f"{marker}\n" "-----END RSA PRIVATE KEY-----\n"
        with self.assertLogs("apps.dependabot.services.github_jwt", level=logging.DEBUG) as cm:
            with self.assertRaises(ItqanError):
                create_github_app_jwt(
                    app_id=1,
                    private_key_pem=bad_pem,
                    now=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
                )
        for record in cm.records:
            self.assertNotIn(marker, record.getMessage())
