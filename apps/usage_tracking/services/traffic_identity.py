"""Pseudonymous, stable client identities (HMAC-SHA256 under USAGE_IDENTITY_KEY).

Stable across days so unique counts work over any range; raw values are never stored.
"""

import hashlib
import hmac

from django.conf import settings


def _identity_key() -> bytes:
    if settings.USAGE_IDENTITY_KEY:
        return settings.USAGE_IDENTITY_KEY.encode()
    return hashlib.sha256(f"usage-identity:{settings.SECRET_KEY}".encode()).digest()


def _hmac(value: str) -> str:
    return hmac.new(_identity_key(), value.encode(), hashlib.sha256).hexdigest()


def listener_id_for(ip: str, user_agent: str, ray_id: str) -> str:
    # Without an IP, fall back to the request itself so IP-less requests never merge.
    return _hmac(f"listener:{ip}|{user_agent}" if ip else f"ray:{ray_id}")


def end_user_id_for(app_key: str, external_user_id: str) -> str:
    return _hmac(f"user:{app_key}|{external_user_id}") if external_user_id else ""


def install_id_for(raw: str) -> str:
    return _hmac(f"install:{raw}") if raw else ""
