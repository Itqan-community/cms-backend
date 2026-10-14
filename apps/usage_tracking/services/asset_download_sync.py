"""Hourly import of asset download data from Cloudflare into events and rollups.

Each UTC hour is replaced as a whole (events, hourly rows, daily rows) and the
watermark only advances after an hour commits, so re-runs never duplicate and a
missed or failed run is picked up by the next one, within Cloudflare's retention.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

from django.conf import settings

from apps.usage_tracking.repositories.asset_downloads import (
    AssetDownloadRepository,
    DownloadEventRow,
    DownloadTotalRow,
)
from apps.usage_tracking.services.cf_downloads_client import (
    CFDownloadEvent,
    CFDownloadTotal,
    CloudflareDownloadsClient,
)
from apps.usage_tracking.services.download_paths import (
    client_hash_for,
    normalize_country,
    parse_download_path,
    status_class_for,
)

logger = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
_MIN_SPLIT = timedelta(minutes=5)
# Keeps the first queried hour clear of the retention edge while the run starts.
_RETENTION_MARGIN = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class SyncResult:
    hours_synced: int
    error: str


def _floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _ceil_hour(value: datetime) -> datetime:
    floored = _floor_hour(value)
    return floored if floored == value else floored + _HOUR


def plan_hours(
    now: datetime,
    watermark: datetime | None,
    oldest_allowed: datetime,
    *,
    lag_minutes: int,
    refresh_hours: int,
    max_slices: int,
) -> list[datetime]:
    """Hour starts to (re)import, oldest first.

    Covers everything from the watermark (or the oldest retained hour on a first run),
    plus the last `refresh_hours` complete hours to pick up late Cloudflare data.
    """
    end = _floor_hour(now - timedelta(minutes=lag_minutes))  # exclusive: hours ending by now - lag
    refresh_start = end - timedelta(hours=refresh_hours)
    if watermark is None:
        start = oldest_allowed  # first run: backfill everything Cloudflare still retains
    else:
        start = max(min(watermark, refresh_start), oldest_allowed)
    hours: list[datetime] = []
    current = start
    while current + _HOUR <= end and len(hours) < max_slices:
        hours.append(current)
        current += _HOUR
    return hours


def fetch_complete[T](
    fetch: Callable[[datetime, datetime, int], list[T]], start: datetime, end: datetime, limit: int
) -> tuple[list[T], bool]:
    """Fetch `[start, end)`, halving the range while a page comes back full."""
    rows = fetch(start, end, limit)
    if len(rows) < limit:
        return rows, False
    if end - start <= _MIN_SPLIT:
        return rows, True
    middle = start + (end - start) / 2
    left, left_truncated = fetch_complete(fetch, start, middle, limit)
    right, right_truncated = fetch_complete(fetch, middle, end, limit)
    return left + right, left_truncated or right_truncated


def build_event_rows(events: list[CFDownloadEvent]) -> tuple[list[DownloadEventRow], int]:
    rows: list[DownloadEventRow] = []
    unmatched = 0
    missing_ip = 0
    for event in events:
        file = parse_download_path(event["clientRequestPath"])
        if file is None:
            unmatched += 1
            continue
        occurred_at = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
        client = event["clientIP"]
        if not client:
            missing_ip += 1
            client = f"ray:{event['rayName']}"  # never merge distinct IP-less requests into one play
        rows.append(
            DownloadEventRow(
                ray_id=event["rayName"],
                occurred_at=occurred_at,
                file=file,
                country=normalize_country(event["clientCountryName"]),
                status_class=status_class_for(event["edgeResponseStatus"]),
                client_hash=client_hash_for(client, occurred_at.date()),
            )
        )
    if missing_ip:
        # Each IP-less request counts as its own play; usually a token-scope change.
        logger.warning(
            "sync_asset_downloads: %d request(s) without clientIP; plays are overcounted (check CF_API_TOKEN scope)",
            missing_ip,
        )
    return rows, unmatched


def build_total_rows(totals: list[CFDownloadTotal]) -> tuple[list[DownloadTotalRow], bool]:
    rows: list[DownloadTotalRow] = []
    sampled = False
    for total in totals:
        sampled = sampled or total["avg"]["sampleInterval"] > 1
        dimensions = total["dimensions"]
        file = parse_download_path(dimensions["clientRequestPath"])
        if file is None:
            continue
        rows.append(
            DownloadTotalRow(
                file=file,
                country=normalize_country(dimensions["clientCountryName"]),
                status_class=status_class_for(dimensions["edgeResponseStatus"]),
                requests=total["count"],
                bytes=total["sum"]["edgeResponseBytes"],
            )
        )
    return rows, sampled


def _build_client() -> CloudflareDownloadsClient:
    return CloudflareDownloadsClient(
        zone_tag=settings.CF_ZONE_ID, api_token=settings.CF_API_TOKEN, hostname=settings.CF_R2_CUSTOM_DOMAIN
    )


def _sync_hour(
    client: CloudflareDownloadsClient, repo: AssetDownloadRepository, hour: datetime, page_size: int
) -> None:
    end = hour + _HOUR
    raw_events, events_truncated = fetch_complete(client.fetch_events, hour, end, page_size)
    raw_totals, totals_truncated = fetch_complete(client.fetch_totals, hour, end, page_size)
    if events_truncated or totals_truncated:
        logger.error("sync_asset_downloads: hour %s still truncated at the 5-minute floor; stored partial data", hour)
    events, unmatched = build_event_rows(raw_events)
    totals, sampled = build_total_rows(raw_totals)
    if sampled:
        logger.warning("sync_asset_downloads: hour %s is sampled by Cloudflare; plays are approximate", hour)
    repo.replace_hour(hour, events, totals, timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES))
    logger.info(
        "sync_asset_downloads: hour=%s events=%d totals=%d unmatched=%d", hour, len(events), len(totals), unmatched
    )


def sync_asset_downloads(now: datetime | None = None) -> SyncResult:
    if not settings.ENABLE_ASSET_DOWNLOAD_SYNC:
        logger.info("sync_asset_downloads: disabled via ENABLE_ASSET_DOWNLOAD_SYNC; skipping")
        return SyncResult(0, "")
    if not (settings.CF_ZONE_ID and settings.CF_API_TOKEN and settings.CF_R2_CUSTOM_DOMAIN):
        logger.warning("sync_asset_downloads: missing CF_ZONE_ID/CF_API_TOKEN/CF_R2_CUSTOM_DOMAIN; skipping")
        return SyncResult(0, "")

    now = now or datetime.now(UTC)
    repo = AssetDownloadRepository()
    if not repo.try_lock():
        logger.info("sync_asset_downloads: another run holds the lock; skipping")
        return SyncResult(0, "")

    hours_synced = 0
    error = ""
    try:
        client = _build_client()
        limits = client.fetch_limits()
        oldest_allowed = _ceil_hour(now - limits.not_older_than + _RETENTION_MARGIN)
        watermark = repo.get_watermark()
        if watermark is not None and watermark < oldest_allowed:
            logger.error(
                "sync_asset_downloads: data lost for [%s, %s) — older than Cloudflare retention",
                watermark,
                oldest_allowed,
            )
        hours = plan_hours(
            now,
            watermark,
            oldest_allowed,
            lag_minutes=settings.ASSET_DOWNLOAD_SYNC_LAG_MINUTES,
            refresh_hours=settings.ASSET_DOWNLOAD_SYNC_REFRESH_HOURS,
            max_slices=settings.ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN,
        )
        for hour in hours:
            _sync_hour(client, repo, hour, limits.max_page_size)
            hours_synced += 1

        if settings.ASSET_DOWNLOAD_EVENT_RETENTION_DAYS:
            repo.purge_events_before(now - timedelta(days=settings.ASSET_DOWNLOAD_EVENT_RETENTION_DAYS))
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("sync_asset_downloads: run failed after %d hour(s)", hours_synced)
    finally:
        try:
            repo.record_run(now, error)
        finally:
            repo.unlock()

    watermark = repo.get_watermark()
    if watermark is None or watermark < now - timedelta(hours=settings.ASSET_DOWNLOAD_SYNC_STALE_HOURS):
        logger.error("sync_asset_downloads: watermark %s is stale (now=%s)", watermark, now)
    return SyncResult(hours_synced, error)
