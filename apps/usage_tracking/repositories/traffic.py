"""Persistence for usage reports: traffic events, rollups, monthly uniques and job state."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta

from django.db import connection, transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncHour

from apps.content.models import Asset, RecitationAyahTiming, RecitationSurahTrack
from apps.usage_tracking.models import (
    AUDIO_KINDS,
    COUNTED_STATUSES,
    EVENT_COUNTED_KINDS,
    FILE_SESSION_KINDS,
    SESSION_STATUSES,
    TRAFFIC_DIMENSIONS,
    LogFileImport,
    R2ObjectReadsHourly,
    SearchEvent,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficMonthlyUniques,
    TrafficSource,
    TrafficStatusClass,
    UniqueMeasure,
    UniqueScope,
    UsageImportState,
)

LOGPUSH_JOB = "logpush"
R2_RECONCILIATION_JOB = "r2_reconciliation"
MAINTENANCE_JOB = "maintenance"
DJANGO_FOLDIN_JOB = "django_foldin"
# Arbitrary constants identifying each job's Postgres advisory lock.
_LOCK_IDS = {
    LOGPUSH_JOB: 7_340_212_027,
    R2_RECONCILIATION_JOB: 7_340_212_028,
    MAINTENANCE_JOB: 7_340_212_029,
    DJANGO_FOLDIN_JOB: 7_340_212_030,
}
_HOUR = timedelta(hours=1)
# Storage URLs are `<CDN host>/media/<file name>` (see `public_media_url`).
_MEDIA_PREFIX = "/media/"
_DIMENSION_COLUMNS = ", ".join(TRAFFIC_DIMENSIONS)

DimensionKey = tuple[object, ...]


def floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _month_start(month: date) -> datetime:
    return datetime(month.year, month.month, 1, tzinfo=UTC)


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


# A file-kind request starts a session unless the same listener requested the same file within
# the window before it. The CTE reads `window` of context before the hour so a play that began
# in the previous hour is not counted again.
_FILE_SESSIONS_SQL = f"""
WITH ordered AS (
    SELECT {_DIMENSION_COLUMNS}, occurred_at,
           LAG(occurred_at) OVER (
               PARTITION BY listener_id, asset_id, kind, surah, asset_version_id
               ORDER BY occurred_at, ray_id
           ) AS previous_at
    FROM {{table}}
    WHERE occurred_at >= %(context_start)s AND occurred_at < %(end)s AND NOT is_bot
      AND status_class = ANY(%(statuses)s) AND kind = ANY(%(kinds)s)
)
SELECT {_DIMENSION_COLUMNS}, COUNT(*)
FROM ordered
WHERE occurred_at >= %(start)s AND (previous_at IS NULL OR occurred_at - previous_at > %(window)s)
GROUP BY {_DIMENSION_COLUMNS}
"""  # nosec B608 — only constant identifiers are interpolated

# An install counts once per install id, asset version and UTC day, in the hour of its first event.
# Requests without an install id (opted out) count individually.
_INSTALL_SESSIONS_SQL = f"""
SELECT {_DIMENSION_COLUMNS}, COUNT(*)
FROM (
    SELECT DISTINCT ON (COALESCE(NULLIF(install_id, ''), ray_id), asset_version_id) *
    FROM {{table}}
    WHERE occurred_at >= %(day_start)s AND occurred_at < %(end)s AND NOT is_bot
      AND kind = %(kind)s AND status_class = ANY(%(statuses)s)
    ORDER BY COALESCE(NULLIF(install_id, ''), ray_id), asset_version_id, occurred_at, ray_id
) first_of_day
WHERE occurred_at >= %(start)s
GROUP BY {_DIMENSION_COLUMNS}
"""  # nosec B608 — only constant identifiers are interpolated

_UNIQUES_SQL = """
SELECT {scope} AS scope_id, COUNT(DISTINCT {identity})
FROM {events} e LEFT JOIN {assets} a ON a.id = e.asset_id
WHERE e.occurred_at >= %(start)s AND e.occurred_at < %(end)s AND NOT e.is_bot
  AND e.status_class = ANY(%(statuses)s) AND e.kind = ANY(%(kinds)s)
GROUP BY 1
HAVING {scope} IS NOT NULL
"""  # nosec B608 — only constant identifiers are interpolated

_UNIQUE_SCOPES = {
    UniqueScope.ALL: "0",
    UniqueScope.ASSET: "e.asset_id",
    UniqueScope.PUBLISHER: "a.publisher_id",
    UniqueScope.APP: "e.app_id",
}
_UNIQUE_MEASURES: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    UniqueMeasure.LISTENERS: (AUDIO_KINDS, SESSION_STATUSES, "e.listener_id"),
    UniqueMeasure.DOWNLOADERS: (
        (TrafficKind.VERSION_FILE, TrafficKind.GALLERY_DOWNLOAD),
        SESSION_STATUSES,
        "e.listener_id",
    ),
    UniqueMeasure.INSTALLS: (
        (TrafficKind.CLI_INSTALL,),
        COUNTED_STATUSES,
        "COALESCE(NULLIF(e.install_id, ''), e.ray_id)",
    ),
    UniqueMeasure.END_USERS: ((TrafficKind.API_CALL,), COUNTED_STATUSES, "NULLIF(e.end_user_id, '')"),
}


class TrafficRepository:
    # -- import bookkeeping -------------------------------------------------
    def imported_keys(self, keys: Iterable[str]) -> set[str]:
        return set(LogFileImport.objects.filter(key__in=list(keys)).values_list("key", flat=True))

    def store_file(self, key: str, events: list[TrafficEvent], error: str = "", hours: Iterable[datetime] = ()) -> None:
        """Insert a file's events and record the file in one transaction (re-runs never double-count).

        `hours` (the rollup hours the events touch) stay pending until `mark_rolled_up`.
        """
        hours = sorted(hours)
        with transaction.atomic():
            TrafficEvent.objects.bulk_create(events, ignore_conflicts=True, batch_size=2000)
            LogFileImport.objects.create(
                key=key,
                rows=len(events),
                error=error,
                first_hour=hours[0] if hours else None,
                last_hour=hours[-1] if hours else None,
                rolled_up=not hours,
            )

    def pending_rollups(self) -> tuple[list[int], set[datetime]]:
        """Files whose hours are not rebuilt yet, and every hour in their ranges."""
        ids: list[int] = []
        hours: set[datetime] = set()
        for file_id, first, last in LogFileImport.objects.filter(rolled_up=False).values_list(
            "id", "first_hour", "last_hour"
        ):
            ids.append(file_id)
            hour = first
            while hour <= last:
                hours.add(hour)
                hour += _HOUR
        return ids, hours

    def mark_rolled_up(self, file_ids: list[int]) -> None:
        LogFileImport.objects.filter(id__in=file_ids).update(rolled_up=True)

    # -- rollups -------------------------------------------------------------
    def rebuild_hour(self, hour: datetime, play_window: timedelta) -> None:
        """Replace the hour's rollup rows (and its day's) from events, atomically."""
        hour = floor_hour(hour)
        end = hour + _HOUR
        with transaction.atomic():
            metrics: dict[DimensionKey, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
            for row in self._totals(hour, end):
                entry = metrics[tuple(row[dimension] for dimension in TRAFFIC_DIMENSIONS)]
                entry[0] += row["total_requests"]
                entry[1] += row["total_bytes"] or 0
                if row["kind"] in EVENT_COUNTED_KINDS:
                    entry[2] += row["total_requests"]
            for key, sessions in self._sessions(hour, end, play_window).items():
                metrics[key][2] += sessions
            for key, seconds in self._listened_seconds(hour, end).items():
                metrics[key][3] += seconds

            TrafficHourly.objects.filter(hour=hour).delete()
            TrafficHourly.objects.bulk_create(
                [
                    TrafficHourly(
                        hour=hour,
                        **dict(zip(TRAFFIC_DIMENSIONS, key, strict=True)),
                        requests=requests,
                        bytes=bytes_,
                        sessions=sessions,
                        listened_seconds=listened,
                    )
                    for key, (requests, bytes_, sessions, listened) in metrics.items()
                ]
            )
            self._rebuild_day(hour.date())

    def _totals(self, start: datetime, end: datetime):
        return (
            TrafficEvent.objects.filter(
                occurred_at__gte=start, occurred_at__lt=end, is_bot=False, status_class__in=COUNTED_STATUSES
            )
            .values(*TRAFFIC_DIMENSIONS)
            .annotate(total_requests=Count("id"), total_bytes=Sum("bytes"))
            .order_by()
        )

    def _listened_seconds(self, start: datetime, end: datetime) -> dict[DimensionKey, int]:
        """Seconds of audio delivered per dimension key: bytes x duration / size of the requested file.

        Paths that are not a stored surah track or ayah file (renamed, deleted) add nothing.
        """
        rows = list(
            TrafficEvent.objects.filter(
                occurred_at__gte=start,
                occurred_at__lt=end,
                is_bot=False,
                status_class__in=SESSION_STATUSES,
                kind__in=AUDIO_KINDS,
                bytes__gt=0,
            )
            .values(*TRAFFIC_DIMENSIONS, "path")
            .annotate(total_bytes=Sum("bytes"))
            .order_by()
        )
        names = {row["path"][len(_MEDIA_PREFIX) :] for row in rows if row["path"].startswith(_MEDIA_PREFIX)}
        assets = {row["asset_id"] for row in rows if row["asset_id"] is not None}
        surahs = {row["surah"] for row in rows if row["surah"] is not None}
        ms_per_byte: dict[str, float] = {}
        if names and assets and surahs:
            # Narrowed by (asset, surah) first: both are indexed, the file name is not.
            tracks = RecitationSurahTrack.objects.filter(asset_id__in=assets, surah_number__in=surahs)
            ayahs = RecitationAyahTiming.objects.filter(track__in=tracks)
            for queryset in (tracks, ayahs):
                for name, duration_ms, size_bytes in queryset.filter(
                    audio_file__in=names, size_bytes__gt=0, duration_ms__gt=0
                ).values_list("audio_file", "duration_ms", "size_bytes"):
                    ms_per_byte[_MEDIA_PREFIX + name] = duration_ms / size_bytes
        totals: dict[DimensionKey, float] = defaultdict(float)
        for row in rows:
            if rate := ms_per_byte.get(row["path"]):
                totals[tuple(row[dimension] for dimension in TRAFFIC_DIMENSIONS)] += row["total_bytes"] * rate / 1000
        return {key: round(seconds) for key, seconds in totals.items()}

    def _sessions(self, hour: datetime, end: datetime, play_window: timedelta) -> dict[DimensionKey, int]:
        table = TrafficEvent._meta.db_table
        sessions: dict[DimensionKey, int] = defaultdict(int)
        with connection.cursor() as cursor:
            cursor.execute(
                _FILE_SESSIONS_SQL.format(table=table),
                {
                    "context_start": hour - play_window,
                    "start": hour,
                    "end": end,
                    "window": play_window,
                    "statuses": list(SESSION_STATUSES),
                    "kinds": list(FILE_SESSION_KINDS),
                },
            )
            for row in cursor.fetchall():
                sessions[tuple(row[:-1])] += int(row[-1])
            cursor.execute(
                _INSTALL_SESSIONS_SQL.format(table=table),
                {
                    "day_start": datetime.combine(hour.date(), time.min, tzinfo=UTC),
                    "start": hour,
                    "end": end,
                    "kind": TrafficKind.CLI_INSTALL.value,
                    "statuses": list(COUNTED_STATUSES),
                },
            )
            for row in cursor.fetchall():
                sessions[tuple(row[:-1])] += int(row[-1])
        return sessions

    def _rebuild_day(self, day: date) -> None:
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        rows = (
            TrafficHourly.objects.filter(hour__gte=day_start, hour__lt=day_start + timedelta(days=1))
            .values(*TRAFFIC_DIMENSIONS)
            .annotate(
                total_requests=Sum("requests"),
                total_bytes=Sum("bytes"),
                total_sessions=Sum("sessions"),
                total_listened=Sum("listened_seconds"),
            )
            .order_by()
        )
        TrafficDaily.objects.filter(day=day).delete()
        TrafficDaily.objects.bulk_create(
            [
                TrafficDaily(
                    day=day,
                    **{dimension: row[dimension] for dimension in TRAFFIC_DIMENSIONS},
                    requests=row["total_requests"],
                    bytes=row["total_bytes"],
                    sessions=row["total_sessions"],
                    listened_seconds=row["total_listened"],
                )
                for row in rows
            ]
        )

    def rebuild_month_uniques(self, month: date) -> None:
        start, end = _month_start(month), _month_start(_next_month(month))
        rows: list[TrafficMonthlyUniques] = []
        with connection.cursor() as cursor:
            for measure, (kinds, statuses, identity) in _UNIQUE_MEASURES.items():
                for scope, scope_expr in _UNIQUE_SCOPES.items():
                    sql = _UNIQUES_SQL.format(
                        scope=scope_expr,
                        identity=identity,
                        events=TrafficEvent._meta.db_table,
                        assets=Asset._meta.db_table,
                    )
                    cursor.execute(sql, {"start": start, "end": end, "kinds": list(kinds), "statuses": list(statuses)})
                    rows.extend(
                        TrafficMonthlyUniques(
                            month=start.date(), scope=scope, scope_id=int(scope_id), measure=measure, count=int(count)
                        )
                        for scope_id, count in cursor.fetchall()
                        if count
                    )
        with transaction.atomic():
            TrafficMonthlyUniques.objects.filter(month=start.date()).delete()
            TrafficMonthlyUniques.objects.bulk_create(rows)

    def event_hours_since(self, start: datetime) -> list[datetime]:
        return list(
            TrafficEvent.objects.filter(occurred_at__gte=start)
            .annotate(hour=TruncHour("occurred_at", tzinfo=UTC))
            .values_list("hour", flat=True)
            .distinct()
            .order_by("hour")
        )

    def purge_events_before(self, cutoff: datetime) -> int:
        deleted, _ = TrafficEvent.objects.filter(occurred_at__lt=cutoff).delete()
        SearchEvent.objects.filter(occurred_at__lt=cutoff).delete()
        return deleted

    # -- reconciliation -------------------------------------------------------
    def edge_requests_by_object(self, hour: datetime) -> dict[str, int]:
        hour = floor_hour(hour)
        rows = (
            TrafficEvent.objects.filter(
                source=TrafficSource.EDGE,
                occurred_at__gte=hour,
                occurred_at__lt=hour + _HOUR,
                kind__in=FILE_SESSION_KINDS,
                status_class__in=(*SESSION_STATUSES, TrafficStatusClass.SUCCESS),
            )
            .values("path")
            .annotate(total=Count("id"))
            .order_by()
        )
        return {row["path"]: row["total"] for row in rows}

    def replace_r2_reads(self, hour: datetime, rows: list[R2ObjectReadsHourly]) -> None:
        hour = floor_hour(hour)
        with transaction.atomic():
            R2ObjectReadsHourly.objects.filter(hour=hour).delete()
            R2ObjectReadsHourly.objects.bulk_create(rows)
            state, _ = UsageImportState.objects.select_for_update().get_or_create(key=R2_RECONCILIATION_JOB)
            if state.watermark is None or hour + _HOUR > state.watermark:
                state.watermark = hour + _HOUR
                state.save(update_fields=["watermark", "updated_at"])

    # -- job state ------------------------------------------------------------
    def try_lock(self, job: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_IDS[job]])
            return bool(cursor.fetchone()[0])

    def unlock(self, job: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_IDS[job]])

    def get_state(self, key: str) -> UsageImportState:
        state, _ = UsageImportState.objects.get_or_create(key=key)
        return state

    def set_cursor(self, key: str, cursor: int, *, traffic_cursor: int) -> None:
        UsageImportState.objects.update_or_create(
            key=key, defaults={"cursor": cursor, "traffic_cursor": traffic_cursor}
        )

    def get_watermark(self, key: str) -> datetime | None:
        return UsageImportState.objects.filter(key=key).values_list("watermark", flat=True).first()

    def set_watermark(self, key: str, value: datetime) -> None:
        UsageImportState.objects.update_or_create(key=key, defaults={"watermark": value})

    def record_run(self, key: str, now: datetime, error: str) -> None:
        UsageImportState.objects.update_or_create(key=key, defaults={"last_run_at": now, "last_error": error})
