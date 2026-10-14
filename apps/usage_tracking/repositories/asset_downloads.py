"""Persistence for asset download statistics: events, rollups and sync state."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from django.db import connection, transaction
from django.db.models import Sum

from apps.usage_tracking.models import (
    ROLLUP_DIMENSIONS,
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
    UsageSyncState,
)
from apps.usage_tracking.services.download_paths import DownloadFile

SYNC_KEY = "cf_asset_downloads"
# Arbitrary constant identifying this job's Postgres advisory lock.
_ADVISORY_LOCK_ID = 7_340_212_026

DimensionKey = tuple[int, str, int | None, int | None, str, str]


@dataclass(frozen=True, slots=True)
class DownloadEventRow:
    ray_id: str
    occurred_at: datetime
    file: DownloadFile
    country: str
    status_class: str
    client_hash: str


@dataclass(frozen=True, slots=True)
class DownloadTotalRow:
    file: DownloadFile
    country: str
    status_class: str
    requests: int
    bytes: int


def _key(file: DownloadFile, country: str, status_class: str) -> DimensionKey:
    return (file.asset_id, str(file.file_kind), file.surah, file.asset_version_id, country, str(status_class))


# A request starts a play unless the same client requested the same file within the
# window before it. Only requests that delivered content (200/206) take part, so 404s
# and other failures never count as plays. The CTE reads `window` of context before the
# hour so a play that began in the previous hour is not counted again.
_PLAYS_SQL = """
WITH ordered AS (
    SELECT occurred_at, asset_id, file_kind, surah, asset_version_id, country, status_class,
           LAG(occurred_at) OVER (
               PARTITION BY client_hash, asset_id, file_kind, surah, asset_version_id
               ORDER BY occurred_at, ray_id
           ) AS previous_at
    FROM {table}
    WHERE occurred_at >= %(context_start)s AND occurred_at < %(end)s
      AND status_class IN (%(full)s, %(partial)s)
)
SELECT asset_id, file_kind, surah, asset_version_id, country, status_class, COUNT(*)
FROM ordered
WHERE occurred_at >= %(start)s AND (previous_at IS NULL OR occurred_at - previous_at > %(window)s)
GROUP BY asset_id, file_kind, surah, asset_version_id, country, status_class
"""


class AssetDownloadRepository:
    def get_watermark(self) -> datetime | None:
        return UsageSyncState.objects.filter(key=SYNC_KEY).values_list("watermark", flat=True).first()

    def try_lock(self) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [_ADVISORY_LOCK_ID])
            return bool(cursor.fetchone()[0])

    def unlock(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_ADVISORY_LOCK_ID])

    def replace_hour(
        self,
        hour: datetime,
        events: list[DownloadEventRow],
        totals: list[DownloadTotalRow],
        play_window: timedelta,
    ) -> None:
        """Replace everything stored for `hour` and advance the watermark, atomically."""
        end = hour + timedelta(hours=1)
        with transaction.atomic():
            AssetDownloadEvent.objects.filter(occurred_at__gte=hour, occurred_at__lt=end).delete()
            AssetDownloadEvent.objects.bulk_create(
                [
                    AssetDownloadEvent(
                        ray_id=event.ray_id,
                        occurred_at=event.occurred_at,
                        asset_id=event.file.asset_id,
                        file_kind=event.file.file_kind,
                        surah=event.file.surah,
                        asset_version_id=event.file.asset_version_id,
                        country=event.country,
                        status_class=event.status_class,
                        client_hash=event.client_hash,
                    )
                    for event in events
                ],
                ignore_conflicts=True,
            )
            self._rebuild_hourly(hour, totals, play_window)
            self._rebuild_daily(hour)
            self._advance_watermark(end)

    def record_run(self, now: datetime, error: str) -> None:
        UsageSyncState.objects.update_or_create(key=SYNC_KEY, defaults={"last_run_at": now, "last_error": error})

    def purge_events_before(self, cutoff: datetime) -> int:
        deleted, _ = AssetDownloadEvent.objects.filter(occurred_at__lt=cutoff).delete()
        return deleted

    def _plays(self, hour: datetime, play_window: timedelta) -> dict[DimensionKey, int]:
        params = {
            "context_start": hour - play_window,
            "start": hour,
            "end": hour + timedelta(hours=1),
            "window": play_window,
            "full": AssetDownloadStatusClass.FULL.value,
            "partial": AssetDownloadStatusClass.PARTIAL.value,
        }
        with connection.cursor() as cursor:
            cursor.execute(_PLAYS_SQL.format(table=AssetDownloadEvent._meta.db_table), params)
            return {tuple(row[:6]): int(row[6]) for row in cursor.fetchall()}

    def _rebuild_hourly(self, hour: datetime, totals: list[DownloadTotalRow], play_window: timedelta) -> None:
        metrics: dict[DimensionKey, list[int]] = defaultdict(lambda: [0, 0, 0])
        for total in totals:
            entry = metrics[_key(total.file, total.country, total.status_class)]
            entry[0] += total.requests
            entry[1] += total.bytes
        for key, plays in self._plays(hour, play_window).items():
            metrics[key][2] += plays

        AssetDownloadHourly.objects.filter(hour=hour).delete()
        AssetDownloadHourly.objects.bulk_create(
            [
                AssetDownloadHourly(
                    hour=hour,
                    **dict(zip(ROLLUP_DIMENSIONS, key, strict=True)),
                    requests=requests,
                    bytes=bytes_,
                    plays=plays,
                )
                for key, (requests, bytes_, plays) in metrics.items()
            ]
        )

    def _rebuild_daily(self, hour: datetime) -> None:
        day = hour.astimezone(UTC).date()
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        rows = (
            AssetDownloadHourly.objects.filter(hour__gte=day_start, hour__lt=day_start + timedelta(days=1))
            .values(*ROLLUP_DIMENSIONS)
            .annotate(total_requests=Sum("requests"), total_bytes=Sum("bytes"), total_plays=Sum("plays"))
        )
        AssetDownloadDaily.objects.filter(day=day).delete()
        AssetDownloadDaily.objects.bulk_create(
            [
                AssetDownloadDaily(
                    day=day,
                    **{dimension: row[dimension] for dimension in ROLLUP_DIMENSIONS},
                    requests=row["total_requests"],
                    bytes=row["total_bytes"],
                    plays=row["total_plays"],
                )
                for row in rows
            ]
        )

    def _advance_watermark(self, candidate: datetime) -> None:
        state, _ = UsageSyncState.objects.select_for_update().get_or_create(key=SYNC_KEY)
        if state.watermark is None or candidate > state.watermark:
            state.watermark = candidate
            state.save(update_fields=["watermark", "updated_at"])
