"""GitHub App JWT generation for the Itqan Dependabot updater.

Signs short-lived (max 10 minute) RS256 JWTs that authenticate as a GitHub
App. The JWT is exchanged at ``POST /app/installations/{id}/access_tokens``
for a per-installation access token.

Security rules:
- The private key value never appears in any exception, log line, or
  returned value other than the function argument itself.
- The generated JWT never appears in any log line.
- The only side effects are ``logger.info`` / ``logger.error`` and the
  signing call to ``pyjwt``.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging

import jwt

from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

# GitHub App JWTs cannot exceed a 10-minute lifetime. Hard-capped so an
# accidental over-length issuance is impossible.
# https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
MAX_LIFETIME_SECONDS = 600

# Sentinel for "use wall clock" when no explicit ``now`` is provided.
_UNSET: object = object()


def create_github_app_jwt(
    *,
    app_id: int,
    private_key_pem: str,
    now: datetime | object = _UNSET,
) -> str:
    """Issue a GitHub App JWT signed with the given RSA private key.

    Args:
        app_id: GitHub App ID. Must be a positive integer.
        private_key_pem: PEM-encoded RSA private key as text. May be the
            raw value or one already loaded by
            ``config.settings.base.read_file``.
        now: Optional timezone-aware UTC ``datetime`` for testability.
            Defaults to ``datetime.now(tz=UTC)``.

    Returns:
        A signed RS256 JWT string with claims ``iat``, ``exp``, ``iss``.

    Raises:
        ItqanError: With ``error_name == "github_app_misconfigured"`` and
            ``status_code == 500`` on any configuration problem. The
            private key value and the issued JWT are never included in
            the exception message or ``extra`` payload.
    """
    if not isinstance(app_id, int) or isinstance(app_id, bool) or app_id <= 0:
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub App ID must be a positive integer.",
            500,
        )
    if not isinstance(private_key_pem, str) or not private_key_pem.strip():
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub App private key is not configured.",
            500,
        )

    if now is _UNSET:
        now = datetime.now(tz=UTC)
    elif not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ItqanError(
            "github_app_misconfigured",
            "JWT issuance time must be timezone-aware UTC.",
            500,
        )
    else:
        now = now.astimezone(UTC)

    issued_at = int(now.timestamp())
    claims = {
        "iat": issued_at,
        "exp": issued_at + MAX_LIFETIME_SECONDS,
        "iss": str(app_id),
    }

    try:
        token = jwt.encode(claims, private_key_pem, algorithm="RS256")
    except (jwt.InvalidKeyError, jwt.exceptions.InvalidAlgorithmError, ValueError, TypeError) as exc:
        # pyjwt raises InvalidKeyError for bad PEMs; cryptography raises
        # ValueError for malformed keys. The key material must not be
        # echoed back to the caller or to the log.
        logger.error("github_jwt: failed to sign app_jwt [app_id=%d, error_type=%s]", app_id, type(exc).__name__)
        raise ItqanError(
            "github_app_misconfigured",
            "GitHub App private key could not be parsed.",
            500,
        ) from None

    logger.info("github_jwt: issued app_jwt [app_id=%d]", app_id)
    return token
