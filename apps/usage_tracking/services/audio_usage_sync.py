"""Pulls `.mp3` edge-request usage from Cloudflare Analytics and imports it to Mixpanel.

Runs periodically over aligned, non-overlapping UTC windows. Each Mixpanel event's
`$insert_id` is derived deterministically from (window, path, dimensions), so a rerun
or retry over the same window dedups on Mixpanel's `/import` side instead of creating
duplicate rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any
import uuid

from django.conf import settings

from apps.usage_tracking.repositories.asset_usage import AssetDimensions, AssetUsageRepository
from apps.usage_tracking.services.cf_analytics_client import CFUsageRow, CloudflareAnalyticsClient
from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

logger = logging.getLogger(__name__)

# One event = one aggregated CF row (a 6h window grouped by path/country/device/status/cache),
# not a single HTTP request -- `request_count` carries the underlying request volume.
EVENT_NAME = "audio_usage_summary"

# Fixed namespace for deriving Mixpanel `$insert_id`s -- any stable UUID works, it
# only needs to never change so the same (window, path, dims) always hashes to the
# same insert_id, making reruns/retries dedup safely.
_INSERT_ID_NAMESPACE = uuid.UUID("3f6f8e2a-9d1c-4b7e-8a2f-6c1d9e4b7a3f")

# Matches the path scheme built by `upload_to_recitation_surah_track_files`
# (apps/core/uploads.py), with `/media/` prefix on the served URL. mp3-only:
# production recitation tracks are all mp3, matching the CF query's `pathLike="%.mp3"`.
_AUDIO_PATH_RE = re.compile(r"(?:/media)?/uploads/assets/(?P<asset_id>\d+)/recitations/(?P<surah>\d+)\.mp3$")

# CF cache statuses that mean the edge served bytes without hitting the origin.
_CACHE_HIT_STATUSES = {"hit", "stale", "revalidated", "expired", "updating"}


@dataclass(frozen=True, slots=True)
class ParsedAudioPath:
    asset_id: int
    surah: int


@dataclass(frozen=True, slots=True)
class SyncWindow:
    start: datetime
    end: datetime

    @property
    def start_epoch(self) -> int:
        return int(self.start.timestamp())

    @property
    def end_epoch(self) -> int:
        return int(self.end.timestamp())

    @property
    def start_iso(self) -> str:
        return self.start.strftime("%Y-%m-%d %H:%M UTC")

    @property
    def end_iso(self) -> str:
        return self.end.strftime("%Y-%m-%d %H:%M UTC")


def parse_audio_path(path: str) -> ParsedAudioPath | None:
    """Extract `asset_id`/`surah` from a `.mp3` request path, or None if it doesn't match."""
    match = _AUDIO_PATH_RE.search(path)
    if not match:
        return None
    return ParsedAudioPath(asset_id=int(match.group("asset_id")), surah=int(match.group("surah")))


def compute_time_window(now: datetime, window_hours: int = 6) -> SyncWindow:
    """Return the last fully-elapsed, aligned `window_hours` UTC window ending at or before `now`.

    e.g. with `window_hours=6`, a run at 06:05 UTC returns `(00:00Z, 06:00Z)`. Built
    from an explicit UTC `now` (never the Celery beat timezone) so window boundaries
    -- and therefore `$insert_id`s -- are deterministic regardless of `CELERY_TIMEZONE`.

    `window_hours` must evenly divide 24, or windows would not tile a day (e.g. 5
    would never produce a `20:00-01:00` window, silently dropping hours).
    """
    if window_hours <= 0 or 24 % window_hours:
        raise ValueError(f"window_hours must divide 24 evenly, got {window_hours}")

    now_utc = now.astimezone(UTC)
    aligned_hour = (now_utc.hour // window_hours) * window_hours
    window_end = now_utc.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
    window_start = window_end - timedelta(hours=window_hours)
    return SyncWindow(start=window_start, end=window_end)


def load_assets_lookup(asset_ids: set[int]) -> dict[int, AssetDimensions]:
    return AssetUsageRepository().get_dimensions_by_ids(asset_ids)


def build_insert_id(window_start: datetime, path: str, country: str, device: str, status: int, cache: str) -> str:
    key = f"{int(window_start.timestamp())}|{path}|{country}|{device}|{status}|{cache}"
    return str(uuid.uuid5(_INSERT_ID_NAMESPACE, key))


def _dimensions_key(dims: CFUsageRow) -> tuple[str, str, str, int, str]:
    values = dims["dimensions"]
    return (
        values["clientRequestPath"],
        values["clientCountryName"],
        values["clientDeviceType"],
        values["edgeResponseStatus"],
        values["cacheStatus"],
    )


def _build_event_properties(
    row: CFUsageRow,
    asset: AssetDimensions | None,
    parsed: ParsedAudioPath | None,
    window: SyncWindow,
) -> dict[str, Any]:
    path, country, device, status, cache = _dimensions_key(row)
    bytes_served = row["sum"]["edgeResponseBytes"]
    insert_id = build_insert_id(window.start, path, country, device, status, cache)

    return {
        "distinct_id": "",  # intentional: these are aggregate, non-user events, not tied to a person
        "time": window.start_epoch,
        "$insert_id": insert_id,
        "request_count": row["count"],
        "bytes": bytes_served,
        "egress_mb": round(bytes_served / (1024 * 1024), 4),
        "asset_id": parsed.asset_id if parsed else None,
        "asset_name": asset.name if asset else None,
        "surah": parsed.surah if parsed else None,
        "publisher_id": asset.publisher_id if asset else None,
        "publisher_name": asset.publisher_name if asset else None,
        "reciter": asset.reciter if asset else None,
        "riwayah": asset.riwayah if asset else None,
        "qiraah": asset.qiraah if asset else None,
        "country": country,
        "device_type": device,
        "edge_status": status,
        "cache_status": cache,
        "is_cache_hit": cache in _CACHE_HIT_STATUSES,
        "window_start": window.start_epoch,
        "window_end": window.end_epoch,
        "window_start_iso": window.start_iso,
        "window_end_iso": window.end_iso,
        "event_time_iso": window.start_iso,
        "source": "cloudflare_r2",
        "enriched": asset is not None,
    }


def build_events(
    rows: list[CFUsageRow],
    assets_lookup: dict[int, AssetDimensions],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    window = SyncWindow(start=window_start, end=window_end)
    events = []
    for row in rows:
        parsed = parse_audio_path(row["dimensions"]["clientRequestPath"])
        asset = assets_lookup.get(parsed.asset_id) if parsed else None
        properties = _build_event_properties(row, asset, parsed, window)
        events.append({"event": EVENT_NAME, "properties": properties})
    return events


def _build_cf_client() -> CloudflareAnalyticsClient:
    return CloudflareAnalyticsClient(zone_tag=settings.CF_ZONE_ID, api_token=settings.CF_API_TOKEN)


def _build_ingest_client() -> MixpanelIngestClient:
    return MixpanelIngestClient(
        token=settings.MIXPANEL_PROJECT_TOKEN,
        ingest_host=settings.MIXPANEL_INGEST_HOST,
        enabled=settings.MIXPANEL_ENABLED,
        project_id=settings.MIXPANEL_PROJECT_ID,
    )


def sync_audio_usage(window_hours: int = 6) -> int:
    """Run one sync cycle: fetch the last elapsed `window_hours` window from CF and import it to Mixpanel."""
    if not settings.ENABLE_AUDIO_USAGE_SYNC:
        logger.info("sync_audio_usage: disabled via ENABLE_AUDIO_USAGE_SYNC; skipping")
        return 0

    if not (settings.CF_ZONE_ID and settings.CF_API_TOKEN and settings.CF_R2_CUSTOM_DOMAIN):
        logger.warning(
            "sync_audio_usage: missing Cloudflare configuration (CF_ZONE_ID/CF_API_TOKEN/CF_R2_CUSTOM_DOMAIN); skipping"
        )
        return 0

    window = compute_time_window(datetime.now(UTC), window_hours=window_hours)
    logger.info(
        "sync_audio_usage: start window=[%s, %s) window_hours=%d host=%s zone=%s",
        window.start.isoformat(),
        window.end.isoformat(),
        window_hours,
        settings.CF_R2_CUSTOM_DOMAIN,
        settings.CF_ZONE_ID,
    )

    cf_client = _build_cf_client()
    result = cf_client.fetch_audio_usage(hostname=settings.CF_R2_CUSTOM_DOMAIN, start=window.start, end=window.end)
    logger.info(
        "sync_audio_usage: CF returned %d row(s) for window=[%s, %s)",
        len(result.rows),
        window.start.isoformat(),
        window.end.isoformat(),
    )
    if result.truncated:
        logger.warning(
            "sync_audio_usage: CF result hit the query limit for window %s-%s; window may need finer "
            "slicing to avoid dropped rows",
            window.start.isoformat(),
            window.end.isoformat(),
        )
    if not result.rows:
        logger.info("sync_audio_usage: no rows to import; done")
        return 0

    asset_ids = {
        parsed.asset_id for row in result.rows if (parsed := parse_audio_path(row["dimensions"]["clientRequestPath"]))
    }
    assets_lookup = load_assets_lookup(asset_ids)
    logger.info(
        "sync_audio_usage: parsed %d distinct asset_id(s); enriched %d from DB",
        len(asset_ids),
        len(assets_lookup),
    )

    events = build_events(result.rows, assets_lookup, window.start, window.end)
    logger.info("sync_audio_usage: built %d Mixpanel event(s); importing", len(events))

    ingest_client = _build_ingest_client()
    imported = ingest_client.import_events(events)
    logger.info(
        "sync_audio_usage: done window=[%s, %s) rows=%d events=%d imported=%d",
        window.start.isoformat(),
        window.end.isoformat(),
        len(result.rows),
        len(events),
        imported,
    )
    return imported
