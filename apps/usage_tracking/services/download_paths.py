"""Maps Cloudflare request paths for asset files to (asset, file kind, surah/version).

Path shapes come from `apps/core/uploads.py`, served under `/media/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import hmac
import re

from django.conf import settings

from apps.usage_tracking.models import AssetDownloadFileKind, AssetDownloadStatusClass

# GraphQL `clientRequestPath_like` filter covering every asset file; the parser drops
# thumbnails/previews that also live under this prefix.
ASSET_PATH_LIKE = "/media/uploads/assets/%"

_SURAH_RE = re.compile(r"^/media/uploads/assets/(?P<asset_id>\d+)/recitations/(?P<surah>\d{3})\.[A-Za-z0-9]+$")
_AYAH_RE = re.compile(
    r"^/media/uploads/assets/(?P<asset_id>\d+)/recitations/\d+/(?P<surah>\d{3})/ayah_\d{3}\.[A-Za-z0-9]+$"
)
_VERSION_RE = re.compile(r"^/media/uploads/assets/(?P<asset_id>\d+)/versions/(?P<version>[^/]+)/[^/]+$")

_UNKNOWN_COUNTRY = "XX"
# Postgres `integer` upper bound: larger ids cannot be stored and would fail the whole hour.
_MAX_DB_INTEGER = 2_147_483_647
SURAH_RANGE = range(1, 115)


@dataclass(frozen=True, slots=True)
class DownloadFile:
    asset_id: int
    file_kind: str
    surah: int | None
    asset_version_id: int | None


def db_integer(value: str) -> int | None:
    return int(value) if value.isdigit() and int(value) <= _MAX_DB_INTEGER else None


def parse_download_path(path: str) -> DownloadFile | None:
    """Return the file a request path refers to, or None for anything that is not a countable download.

    Request paths are attacker-controlled (anyone can request any URL on the CDN), so ids
    that cannot be stored and surah numbers outside 1-114 are rejected rather than stored.
    """
    if match := _SURAH_RE.match(path) or _AYAH_RE.match(path):
        kind = AssetDownloadFileKind.SURAH if match.re is _SURAH_RE else AssetDownloadFileKind.AYAH
        asset_id = db_integer(match["asset_id"])
        surah = int(match["surah"])
        if asset_id is None or surah not in SURAH_RANGE:
            return None
        return DownloadFile(asset_id, kind, surah, None)
    if match := _VERSION_RE.match(path):
        asset_id = db_integer(match["asset_id"])
        if asset_id is None:
            return None
        # `versions/tmp-xxxx/` paths were uploaded before the version row had a pk.
        return DownloadFile(asset_id, AssetDownloadFileKind.VERSION, None, db_integer(match["version"]))
    return None


def status_class_for(status: int) -> str:
    if status == 200:
        return AssetDownloadStatusClass.FULL
    if status == 206:
        return AssetDownloadStatusClass.PARTIAL
    return AssetDownloadStatusClass.OTHER


def normalize_country(value: str | None) -> str:
    return (value or _UNKNOWN_COUNTRY)[:2].upper()


def client_hash_for(ip: str, day: date) -> str:
    """Pseudonymous client id that cannot be linked across UTC days."""
    key = f"{settings.SECRET_KEY}:{day.isoformat()}".encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()
