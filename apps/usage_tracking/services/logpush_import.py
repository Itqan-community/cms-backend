"""Hourly import of Cloudflare Logpush files (every edge request) from R2 into traffic events.

Files are listed per day folder and skipped once recorded in `LogFileImport`, so missed runs
catch up and re-runs never double-count. Every hour that received events is then rebuilt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import gzip
import logging
import re
import zlib

from django.conf import settings

from apps.content.models import Asset, AssetVersion
from apps.usage_tracking.models import TrafficEvent, TrafficKind, TrafficSource
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.logpush_parser import ParsedRequest, parse_lines
from apps.usage_tracking.services.r2_logs_client import R2LogsClient
from apps.usage_tracking.services.traffic_classify import channel_for, is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import end_user_id_for, install_id_for, listener_id_for
from apps.usage_tracking.services.usage_apps import slug_ids

logger = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
# Folders older than the watermark day minus this are assumed complete.
_RELIST_DAYS = 1
_DAY_FOLDER_RE = re.compile(r"^\d{8}/$")
# Logpush pushes every few minutes; a day folder with nothing newer than this means it stopped.
_STALE_DAYS = 1


@dataclass(frozen=True, slots=True)
class ImportResult:
    files_imported: int
    events: int
    skipped_lines: int
    error: str


class _Resolver:
    """Batch lookups for asset ids and languages the request path does not carry."""

    def __init__(self, parsed: list[ParsedRequest]) -> None:
        version_ids = {p.asset_version_id for p in parsed if p.asset_version_id}
        slugs = {p.asset_slug for p in parsed if p.asset_slug}
        self._versions = {
            row["id"]: (row["asset_id"], row["asset_language__language"] or "")
            for row in AssetVersion.objects.filter(id__in=version_ids).values(
                "id", "asset_id", "asset_language__language"
            )
        }
        self._slugs = dict(Asset.objects.filter(slug__in=slugs).values_list("slug", "id"))
        self._apps = slug_ids(p.app_slug_raw for p in parsed if p.app_slug_raw)

    def asset_id(self, parsed: ParsedRequest) -> int | None:
        if parsed.asset_id is not None:
            return parsed.asset_id
        if parsed.asset_version_id in self._versions:
            return self._versions[parsed.asset_version_id][0]
        return self._slugs.get(parsed.asset_slug)

    def app_id(self, parsed: ParsedRequest) -> int | None:
        return self._apps.get(parsed.app_slug_raw)

    def language(self, parsed: ParsedRequest) -> str:
        return self._versions.get(parsed.asset_version_id, (None, ""))[1]


def build_events(parsed: list[ParsedRequest]) -> list[TrafficEvent]:
    resolver = _Resolver(parsed)
    events: list[TrafficEvent] = []
    missing_ip = 0
    for request in parsed:
        family = ua_family(request.user_agent)
        app_id = resolver.app_id(request)
        if not request.ip:
            missing_ip += 1
        events.append(
            TrafficEvent(
                ray_id=request.ray_id,
                occurred_at=request.occurred_at,
                source=TrafficSource.EDGE,
                kind=request.kind,
                asset_id=resolver.asset_id(request),
                surah=request.surah,
                asset_version_id=request.asset_version_id,
                language=resolver.language(request),
                country=request.country,
                channel=channel_for(
                    request.kind, family, has_install_id=bool(request.install_id_raw), app_identified=app_id is not None
                ),
                platform=platform_for(request.user_agent, family),
                app_id=app_id,
                endpoint=request.endpoint,
                path=request.path,
                app_slug_raw=request.app_slug_raw,
                status_class=request.status_class,
                bytes=request.bytes,
                cache_status=request.cache_status,
                listener_id=listener_id_for(request.ip, request.user_agent, request.ray_id),
                end_user_id=end_user_id_for(request.client_name, request.external_user_id),
                install_id=install_id_for(request.install_id_raw),
                ua_family=family,
                client_name=request.client_name,
                client_version=request.client_version,
                is_bot=is_bot_user_agent(request.user_agent),
            )
        )
    if missing_ip:
        logger.warning("import_logpush: %d request(s) without ClientIP; each counts as its own listener", missing_ip)
    return events


def touched_hours(events: Iterable[TrafficEvent], play_window: timedelta) -> set[datetime]:
    """Hours whose rollups change when these events are added."""
    hours: set[datetime] = set()
    for event in events:
        hour = floor_hour(event.occurred_at)
        hours.add(hour)
        if event.kind == TrafficKind.CLI_INSTALL:
            # An earlier install moves "first of the day" out of later hours of the same day.
            day_end = datetime.combine(hour.date() + timedelta(days=1), time.min, tzinfo=UTC)
            next_hour = hour + _HOUR
            while next_hour < day_end:
                hours.add(next_hour)
                next_hour += _HOUR
        elif event.occurred_at >= hour + _HOUR - play_window:
            hours.add(hour + _HOUR)  # a play may continue into the next hour
    return hours


def _build_client() -> R2LogsClient:
    return R2LogsClient(
        endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT,
        access_key_id=settings.USAGE_LOGS_ACCESS_KEY_ID,
        secret_access_key=settings.USAGE_LOGS_SECRET_ACCESS_KEY,
        bucket=settings.USAGE_LOGS_BUCKET,
    )


def _folder_day(key: str) -> date:
    """`<prefix>YYYYMMDD/...` → that date."""
    return datetime.strptime(key[len(settings.USAGE_LOGS_PREFIX) :][:8], "%Y%m%d").date()


def _rollup_pending(repo: TrafficRepository, play_window: timedelta) -> None:
    file_ids, hours = repo.pending_rollups()
    for hour in sorted(hours):
        repo.rebuild_hour(hour, play_window)
    repo.mark_rolled_up(file_ids)


def _pending_keys(
    client: R2LogsClient, repo: TrafficRepository, watermark: datetime | None
) -> tuple[list[str], list[str]]:
    # Anything other than a `YYYYMMDD/` folder (a stray upload, a test prefix) is ignored.
    folders = [
        folder
        for folder in client.list_day_prefixes(settings.USAGE_LOGS_PREFIX)
        if _DAY_FOLDER_RE.match(folder[len(settings.USAGE_LOGS_PREFIX) :])
    ]
    if watermark is not None:
        oldest = watermark.date() - timedelta(days=_RELIST_DAYS)
        folders = [folder for folder in folders if _folder_day(folder) >= oldest]
    pending: list[str] = []
    for folder in folders:
        keys = client.list_keys(folder)
        done = repo.imported_keys(keys)
        pending.extend(key for key in keys if key not in done)
    return folders, pending


def import_logpush(now: datetime | None = None) -> ImportResult:
    if not settings.ENABLE_USAGE_LOGPUSH_IMPORT:
        logger.info("import_logpush: disabled via ENABLE_USAGE_LOGPUSH_IMPORT; skipping")
        return ImportResult(0, 0, 0, "")
    if not (
        settings.USAGE_LOGS_ACCESS_KEY_ID and settings.USAGE_LOGS_SECRET_ACCESS_KEY and settings.CLOUDFLARE_R2_ENDPOINT
    ):
        logger.warning("import_logpush: missing USAGE_LOGS_* credentials or CLOUDFLARE_R2_ENDPOINT; skipping")
        return ImportResult(0, 0, 0, "")

    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(LOGPUSH_JOB):
        logger.info("import_logpush: another run holds the lock; skipping")
        return ImportResult(0, 0, 0, "")

    files = events_total = skipped_total = 0
    error = ""
    play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
    try:
        _rollup_pending(repo, play_window)  # finish files a previous run stored but did not roll up
        client = _build_client()
        folders, pending = _pending_keys(client, repo, repo.get_watermark(LOGPUSH_JOB))
        batch = pending[: settings.USAGE_LOGPUSH_MAX_FILES_PER_RUN]
        for key in batch:
            try:
                parsed, skipped = parse_lines(client.iter_lines(key))
            # Truncated or non-gzip file. Network errors (timeouts are OSErrors too) propagate
            # instead, leaving the file pending for the next run.
            except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
                logger.error("import_logpush: unreadable file %s: %s", key, exc)
                repo.store_file(key, [], error=f"{type(exc).__name__}: {exc}")
                files += 1
                continue
            events = build_events(parsed)
            repo.store_file(key, events, hours=touched_hours(events, play_window))
            _rollup_pending(repo, play_window)
            files += 1
            events_total += len(events)
            skipped_total += skipped
        remaining = pending[len(batch) :]
        if remaining:
            watermark_day = _folder_day(remaining[0])
        elif folders:
            watermark_day = _folder_day(folders[-1])
        else:
            watermark_day = None
        if watermark_day is not None:
            repo.set_watermark(LOGPUSH_JOB, datetime.combine(watermark_day, time.min, tzinfo=UTC))
        if not folders or _folder_day(folders[-1]) < now.date() - timedelta(days=_STALE_DAYS):
            logger.error(
                "import_logpush: no recent Logpush files under %s (check the Logpush job)", settings.USAGE_LOGS_PREFIX
            )
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("import_logpush: run failed after %d file(s)", files)
    finally:
        try:
            repo.record_run(LOGPUSH_JOB, now, error)
        finally:
            repo.unlock(LOGPUSH_JOB)

    logger.info("import_logpush: files=%d events=%d skipped_lines=%d", files, events_total, skipped_total)
    return ImportResult(files, events_total, skipped_total, error)
