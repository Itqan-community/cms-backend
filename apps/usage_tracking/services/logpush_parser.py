"""Turns Cloudflare Logpush `http_requests` lines into parsed asset requests.

Kept: asset files under /media/uploads/assets/ and public developer-API routes (taken from the
API's own OpenAPI schema, so new routes are covered automatically). Dropped: everything else on
the hosts (portal, CMS API, OAuth, static files, scanners).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import functools
import json
import re
from urllib.parse import parse_qs

from apps.usage_tracking.models import AssetDownloadFileKind, TrafficKind
from apps.usage_tracking.services.download_paths import SURAH_RANGE, db_integer, normalize_country, parse_download_path
from apps.usage_tracking.services.traffic_classify import status_class_for

_FILE_KINDS = {
    AssetDownloadFileKind.SURAH: TrafficKind.AUDIO_SURAH,
    AssetDownloadFileKind.AYAH: TrafficKind.AUDIO_AYAH,
    AssetDownloadFileKind.VERSION: TrafficKind.VERSION_FILE,
}
# OAuth endpoints share the developer API but are not data access.
_EXCLUDED_API_PATHS = frozenset({"/token/", "/revoke/"})
# Epoch values above this are unixnano (Logpush default); below are seconds.
_NANOSECOND_THRESHOLD = 10**11


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    ray_id: str
    occurred_at: datetime
    kind: str
    asset_id: int | None
    surah: int | None
    asset_version_id: int | None
    asset_slug: str
    endpoint: str
    path: str
    country: str
    status_class: str
    bytes: int
    cache_status: str
    ip: str
    user_agent: str
    app_slug_raw: str
    client_name: str
    client_version: str
    external_user_id: str
    install_id_raw: str


@dataclass(frozen=True, slots=True)
class _Route:
    template: str
    pattern: re.Pattern[str]


@functools.cache
def _api_routes() -> tuple[_Route, ...]:
    """Public developer-API routes; literal routes before parameterised ones."""
    from config.developers_api import developers_api  # lazy: loading every public router is not free

    routes = []
    for template in developers_api.get_openapi_schema()["paths"]:
        if template in _EXCLUDED_API_PATHS:
            continue
        regex = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(template))
        routes.append(_Route(template, re.compile(f"^{regex}$")))
    return tuple(sorted(routes, key=lambda route: (route.pattern.groups, -len(route.template))))


_Located = tuple[str, int | None, int | None, int | None, str, str]


def _locate(path: str, params: dict[str, list[str]]) -> _Located | None:
    if file := parse_download_path(path):
        kind = TrafficKind.GALLERY_DOWNLOAD if "download" in params else _FILE_KINDS[file.file_kind]
        return kind, file.asset_id, file.surah, file.asset_version_id, "", ""
    for route in _api_routes():
        if match := route.pattern.match(path):
            values = match.groupdict()
            surah = db_integer(values.get("surah_number", ""))
            return (
                TrafficKind.API_CALL,
                db_integer(values.get("asset_id", "")),
                surah if surah in SURAH_RANGE else None,
                db_integer(values.get("asset_version_id", "")),
                values.get("slug", "")[:100],
                route.template,
            )
    return None


def _timestamp(value: object) -> datetime:
    if isinstance(value, str) and not value.isdigit():
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    number = int(value)  # type: ignore[call-overload]
    return datetime.fromtimestamp(number / 1e9 if number > _NANOSECOND_THRESHOLD else number, tz=UTC)


def _text(value: object, limit: int) -> str:
    # Postgres text cannot hold NUL; one such byte would fail the whole file on every run.
    return str(value or "").replace("\x00", "")[:limit]


def _first(params: dict[str, list[str]], name: str) -> str:
    return (params.get(name) or [""])[0]


def parse_line(line: bytes | str) -> ParsedRequest | None:
    """The request a Logpush line describes, or None when it is malformed or not counted."""
    try:
        record = json.loads(line)
        if not isinstance(record, dict) or not record.get("RayID"):
            return None
        # Only GET fetches content; CORS preflights (OPTIONS) and HEAD probes are not usage.
        if (record.get("ClientRequestMethod") or "GET") != "GET":
            return None
        uri = _text(record.get("ClientRequestURI") or record.get("ClientRequestPath"), 4096)
        path, _, query = uri.partition("?")
        params = parse_qs(query, keep_blank_values=True)
        located = _locate(path, params)
        if located is None:
            return None
        kind, asset_id, surah, version_id, slug, endpoint = located
        headers = record.get("RequestHeaders") or {}
        return ParsedRequest(
            ray_id=_text(record["RayID"], 64),
            occurred_at=_timestamp(record["EdgeStartTimestamp"]),
            kind=kind,
            asset_id=asset_id,
            surah=surah,
            asset_version_id=version_id,
            asset_slug=slug,
            endpoint=endpoint,
            path=path[:512],
            country=normalize_country(record.get("ClientCountry")),
            status_class=status_class_for(int(record.get("EdgeResponseStatus") or 0)),
            bytes=int(record.get("EdgeResponseBytes") or 0),
            cache_status=_text(record.get("CacheCacheStatus"), 16),
            ip=_text(record.get("ClientIP"), 64),
            user_agent=_text(record.get("ClientRequestUserAgent"), 1024),
            app_slug_raw=_first(params, "c")[:64],
            client_name=_text(headers.get("x-client-name"), 64),
            client_version=_text(headers.get("x-client-version"), 32),
            external_user_id=_text(headers.get("x-external-user-id"), 64),
            install_id_raw=_text(headers.get("x-itqan-install-id"), 64),
        )
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None


def parse_lines(lines: Iterable[bytes | str]) -> tuple[list[ParsedRequest], int]:
    parsed: list[ParsedRequest] = []
    skipped = 0
    for line in lines:
        request = parse_line(line)
        if request is None:
            skipped += 1
        else:
            parsed.append(request)
    return parsed, skipped
