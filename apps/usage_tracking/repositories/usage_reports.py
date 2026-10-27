"""Read queries behind the usage reports.

Additive metrics read `TrafficDaily` (or `TrafficHourly` for hourly series and hour-of-week);
unique metrics read `TrafficEvent` (distinct counts are not additive across rollup rows) or,
past event retention, `TrafficMonthlyUniques`. Every function returns plain Python values.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import Any

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import connection
from django.db.models import Count, Exists, F, Max, Min, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import (
    Coalesce,
    ExtractHour,
    ExtractIsoWeekDay,
    Greatest,
    Trunc,
    TruncDay,
    TruncMonth,
    TruncWeek,
)

from apps.content.models import (
    PUBLISHED_VERSION_CATEGORIES,
    Asset,
    AssetLanguage,
    AssetVersion,
    Qiraah,
    RecitationAyahTiming,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    VersionStateChoice,
)
from apps.publishers.models import Publisher
from apps.usage_tracking.models import (
    AUDIO_KINDS,
    COUNTED_STATUSES,
    R2ObjectReadsHourly,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficMonthlyUniques,
    UsageApp,
    UsageImportState,
)
from apps.usage_tracking.repositories.traffic import DJANGO_FOLDIN_JOB, LOGPUSH_JOB

# Report dimension -> rollup/event column. Asset dimensions and `hour_of_week` are computed.
DIMENSION_COLUMNS: dict[str, str] = {
    "asset": "asset_id",
    "surah": "surah",
    "country": "country",
    "channel": "channel",
    "platform": "platform",
    "app": "app_id",
    "version": "asset_version_id",
    "language": "language",
    "kind": "kind",
    "endpoint": "endpoint",
}
# Dimensions read from the event's asset.
ASSET_DIMENSIONS: dict[str, str] = {
    "publisher": "publisher_id",
    "reciter": "reciter_id",
    "riwayah": "riwayah_id",
    "qiraah": "qiraah_id",
}
COMPUTED_DIMENSIONS = (*ASSET_DIMENSIONS, "hour_of_week")
UNKNOWN_COUNTRY = "XX"

Key = str


def day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Period:
    start: date
    end: date  # inclusive

    def daily_q(self) -> Q:
        return Q(day__gte=self.start, day__lte=self.end)

    def hourly_q(self) -> Q:
        return Q(hour__gte=day_start(self.start), hour__lt=day_start(self.end + timedelta(days=1)))

    def events_q(self) -> Q:
        return Q(occurred_at__gte=day_start(self.start), occurred_at__lt=day_start(self.end + timedelta(days=1)))


def _kinds_q(kinds: Sequence[str] | None) -> Q:
    return Q(kind__in=list(kinds)) if kinds is not None else Q()


def _unique_q(kinds: Sequence[str], statuses: Sequence[str], identity: str) -> Q:
    return Q(kind__in=list(kinds), status_class__in=list(statuses)) & ~Q(**{identity: ""})


def _with_dimension(queryset: QuerySet, dimension: str, time_field: str, tz: tzinfo) -> tuple[QuerySet, list[str]]:
    """Annotate `queryset` so `.values(*fields)` groups by `dimension`."""
    if dimension in ASSET_DIMENSIONS:
        value = Asset.objects.filter(pk=OuterRef("asset_id")).values(ASSET_DIMENSIONS[dimension])[:1]
        return queryset.annotate(**{f"d_{dimension}": Subquery(value)}), [f"d_{dimension}"]
    if dimension == "hour_of_week":
        return (
            queryset.annotate(
                d_dow=ExtractIsoWeekDay(time_field, tzinfo=tz),
                d_hour=ExtractHour(time_field, tzinfo=tz),
            ),
            ["d_dow", "d_hour"],
        )
    return queryset, [DIMENSION_COLUMNS[dimension]]


def _in_q(column: str, values: Iterable[Any]) -> Q:
    """`column IN values`, matching NULL too when None is among the values."""
    values = list(values)
    q = Q(**{f"{column}__in": [value for value in values if value is not None]})
    if None in values:
        q |= Q(**{f"{column}__isnull": True})
    return q


def dimension_key(row: dict[str, Any], fields: Sequence[str]) -> Key:
    return "-".join("" if row[field] is None else str(row[field]) for field in fields)


# -- totals --------------------------------------------------------------------------------------


def rollup_totals(
    base_q: Q,
    periods: dict[str, Period],
    metrics: dict[str, tuple[str, Sequence[str] | None]],
    app_kinds: Sequence[str],
    unidentified_channel: str,
) -> dict[str, dict[str, int]]:
    """Per period: each metric's sum, identified integrating apps and unidentified-app sessions."""
    annotations: dict[str, Any] = {}
    for period_name, period in periods.items():
        for metric, (field, kinds) in metrics.items():
            annotations[f"{period_name}__{metric}"] = Coalesce(Sum(field, filter=period.daily_q() & _kinds_q(kinds)), 0)
        annotations[f"{period_name}__apps"] = Count(
            "app_id",
            distinct=True,
            filter=period.daily_q() & Q(app_id__isnull=False, sessions__gt=0, kind__in=list(app_kinds)),
        )
        annotations[f"{period_name}__unidentified"] = Coalesce(
            Sum("sessions", filter=period.daily_q() & Q(channel=unidentified_channel, kind__in=list(app_kinds))), 0
        )
    start = min(period.start for period in periods.values())
    end = max(period.end for period in periods.values())
    row = TrafficDaily.objects.filter(base_q, day__gte=start, day__lte=end).aggregate(**annotations)
    result: dict[str, dict[str, int]] = {name: {} for name in periods}
    for key, value in row.items():
        period_name, metric = key.split("__", 1)
        result[period_name][metric] = int(value or 0)
    return result


def unique_totals(
    base_q: Q, periods: dict[str, Period], metrics: dict[str, tuple[Sequence[str], Sequence[str], str]]
) -> dict[str, dict[str, int]]:
    """Per period: each unique metric's distinct identities, from traffic events."""
    if not periods or not metrics:
        return {name: {} for name in periods}
    annotations = {
        f"{period_name}__{metric}": Count(
            identity, distinct=True, filter=period.events_q() & _unique_q(kinds, statuses, identity)
        )
        for period_name, period in periods.items()
        for metric, (kinds, statuses, identity) in metrics.items()
    }
    start = min(period.start for period in periods.values())
    end = max(period.end for period in periods.values())
    row = TrafficEvent.objects.filter(base_q, Period(start, end).events_q(), is_bot=False).aggregate(**annotations)
    result: dict[str, dict[str, int]] = {name: {} for name in periods}
    for key, value in row.items():
        period_name, metric = key.split("__", 1)
        result[period_name][metric] = int(value or 0)
    return result


def monthly_uniques(
    scope: str, scope_ids: Sequence[int] | None, measure: str, start: date, end: date
) -> dict[date, int]:
    """Monthly distinct counts summed over the scope ids, per month between `start` and `end`."""
    queryset = TrafficMonthlyUniques.objects.filter(
        scope=scope, measure=measure, month__gte=start.replace(day=1), month__lte=end
    )
    if scope_ids is not None:
        queryset = queryset.filter(scope_id__in=list(scope_ids))
    rows = queryset.values("month").annotate(total=Sum("count")).order_by()
    return {row["month"]: int(row["total"]) for row in rows}


# -- series --------------------------------------------------------------------------------------


def _rollup_bucket(granularity: str) -> Any:
    return {"hour": F("hour"), "day": F("day"), "week": TruncWeek("day"), "month": TruncMonth("day")}[granularity]


def rollup_series(
    base_q: Q,
    period: Period,
    field: str,
    kinds: Sequence[str] | None,
    granularity: str,
    dimension: str | None,
) -> list[tuple[Any, Key, int]]:
    """(bucket, dimension key or "", value) rows; hourly rows read `TrafficHourly`."""
    if granularity == "hour":
        queryset = TrafficHourly.objects.filter(base_q, period.hourly_q(), _kinds_q(kinds))
    else:
        queryset = TrafficDaily.objects.filter(base_q, period.daily_q(), _kinds_q(kinds))
    fields: list[str] = []
    if dimension:
        queryset, fields = _with_dimension(queryset, dimension, "hour" if granularity == "hour" else "day", UTC)
    rows = queryset.annotate(bucket=_rollup_bucket(granularity)).values("bucket", *fields).annotate(v=Sum(field))
    return [(row["bucket"], dimension_key(row, fields), int(row["v"] or 0)) for row in rows.order_by()]


def unique_series(
    base_q: Q,
    period: Period,
    unique: tuple[Sequence[str], Sequence[str], str],
    granularity: str,
    dimension: str | None = None,
    only_keys: Iterable[Any] | None = None,
    exclude_keys: Iterable[Any] | None = None,
    group: bool = True,
) -> list[tuple[Any, Key, int]]:
    """Distinct identities per bucket (and dimension), from traffic events.

    `only_keys`/`exclude_keys` (raw values of a single-column dimension) restrict the rows;
    `group=False` keeps one total per bucket over the restricted rows.
    """
    kinds, statuses, identity = unique
    queryset = TrafficEvent.objects.filter(
        base_q, period.events_q(), _unique_q(kinds, statuses, identity), is_bot=False
    )
    fields: list[str] = []
    if dimension:
        queryset, fields = _with_dimension(queryset, dimension, "occurred_at", UTC)
        if only_keys is not None:
            queryset = queryset.filter(_in_q(fields[0], only_keys))
        if exclude_keys is not None:
            queryset = queryset.exclude(_in_q(fields[0], exclude_keys))
        if not group:
            fields = []
    rows = (
        queryset.annotate(bucket=Trunc("occurred_at", granularity, tzinfo=UTC))
        .values("bucket", *fields)
        .annotate(v=Count(identity, distinct=True))
        .order_by()
    )
    return [
        (row["bucket"] if granularity == "hour" else row["bucket"].date(), dimension_key(row, fields), int(row["v"]))
        for row in rows
    ]


# -- groups (breakdowns) -------------------------------------------------------------------------


def rollup_groups(
    base_q: Q, period: Period, field: str, kinds: Sequence[str] | None, dimension: str, tz: tzinfo
) -> dict[Key, tuple[Any, int]]:
    """Dimension key -> (raw value of the first column, sum). Hour-of-week reads hourly rollups."""
    if dimension == "hour_of_week":
        queryset = TrafficHourly.objects.filter(base_q, period.hourly_q(), _kinds_q(kinds))
        time_field = "hour"
    else:
        queryset = TrafficDaily.objects.filter(base_q, period.daily_q(), _kinds_q(kinds))
        time_field = "day"
    queryset, fields = _with_dimension(queryset, dimension, time_field, tz)
    rows = queryset.values(*fields).annotate(v=Sum(field)).order_by()
    return {dimension_key(row, fields): (row[fields[0]], int(row["v"] or 0)) for row in rows}


def unique_groups(
    base_q: Q,
    period: Period,
    unique: tuple[Sequence[str], Sequence[str], str],
    dimension: str,
    tz: tzinfo,
    limit: int | None = None,
    only_keys: Iterable[Any] | None = None,
) -> dict[Key, tuple[Any, int]]:
    kinds, statuses, identity = unique
    queryset = TrafficEvent.objects.filter(
        base_q, period.events_q(), _unique_q(kinds, statuses, identity), is_bot=False
    )
    queryset, fields = _with_dimension(queryset, dimension, "occurred_at", tz)
    if only_keys is not None:
        queryset = queryset.filter(_in_q(fields[0], only_keys))
    rows = queryset.values(*fields).annotate(v=Count(identity, distinct=True)).order_by("-v", *fields)
    if limit is not None:
        rows = rows[:limit]
    return {dimension_key(row, fields): (row[fields[0]], int(row["v"])) for row in rows}


def listeners_per_group(
    base_q: Q, period: Period, kinds: Sequence[str] | None, dimension: str, tz: tzinfo
) -> dict[Key, int]:
    """Distinct listeners per dimension key (privacy floor), over counted non-bot events."""
    return {
        key: count
        for key, (_, count) in unique_groups(
            base_q, period, (kinds or _ALL_KINDS, tuple(COUNTED_STATUSES), "listener_id"), dimension, tz
        ).items()
    }


_ALL_KINDS: tuple[str, ...] = tuple(choice for choice, _ in TrafficEvent._meta.get_field("kind").choices)


# -- export --------------------------------------------------------------------------------------


def export_rows(
    base_q: Q, period: Period, granularity: str, metrics: dict[str, tuple[str, Sequence[str] | None]]
) -> list[dict[str, Any]]:
    """Additive metrics per bucket and asset, ordered by bucket then asset."""
    queryset = (
        TrafficHourly.objects.filter(base_q, period.hourly_q())
        if granularity == "hour"
        else TrafficDaily.objects.filter(base_q, period.daily_q())
    )
    annotations = {
        f"m_{metric}": Coalesce(Sum(field, filter=_kinds_q(kinds)), 0) for metric, (field, kinds) in metrics.items()
    }
    return list(
        queryset.annotate(bucket=_rollup_bucket(granularity))
        .values("bucket", "asset_id")
        .annotate(**annotations)
        .order_by("bucket", "asset_id")
    )


# -- reconciliation ------------------------------------------------------------------------------

_UNSEEN = Greatest(F("reads") - F("edge_requests"), Value(0))


def reconciliation(asset_q: Q, period: Period, limit: int) -> dict[str, Any]:
    queryset = R2ObjectReadsHourly.objects.filter(asset_q, period.hourly_q())
    metrics = {
        "m_reads": Coalesce(Sum("reads"), 0),
        "m_edge": Coalesce(Sum("edge_requests"), 0),
        "m_unseen": Coalesce(Sum(_UNSEEN), 0),
    }
    total = queryset.aggregate(**metrics)
    assets = list(queryset.values("asset_id").annotate(**metrics).order_by("-m_unseen", "asset_id")[:limit])
    days = list(queryset.annotate(bucket=TruncDay("hour", tzinfo=UTC)).values("bucket").annotate(**metrics).order_by())
    return {"total": total, "assets": assets, "days": days}


# -- labels and metadata -------------------------------------------------------------------------


def labels(dimension: str, raw_keys: Iterable[Any]) -> dict[Any, str]:
    ids = [key for key in raw_keys if key is not None]
    if not ids:
        return {}
    if dimension == "asset":
        return dict(Asset.objects.filter(id__in=ids).values_list("id", "name"))
    if dimension == "app":
        return dict(UsageApp.objects.filter(id__in=ids).values_list("id", "name"))
    if dimension == "publisher":
        return dict(Publisher.objects.filter(id__in=ids).values_list("id", "name"))
    if dimension == "version":
        return dict(AssetVersion.objects.filter(id__in=ids).values_list("id", "name"))
    if dimension in _NAMED_MODELS:
        return dict(_NAMED_MODELS[dimension].objects.filter(id__in=ids).values_list("id", "name"))
    return {}


_NAMED_MODELS = {"reciter": Reciter, "riwayah": Riwayah, "qiraah": Qiraah}


def asset_details(asset_ids: Iterable[int | None]) -> dict[int, dict[str, Any]]:
    """Asset id -> name, category, publisher id and publisher name."""
    return {
        row["id"]: row
        for row in Asset.objects.filter(id__in={i for i in asset_ids if i is not None}).values(
            "id", "name", "category", "publisher_id", "publisher__name"
        )
    }


def latest_version_ids(asset_id: int, category: str) -> set[int]:
    """The versions consumers are currently served, one per language (see `Asset.get_published_version`)."""
    if category in PUBLISHED_VERSION_CATEGORIES:
        return set(
            AssetLanguage.objects.filter(asset_id=asset_id, published_version__isnull=False).values_list(
                "published_version_id", flat=True
            )
        )
    return set(
        AssetVersion.objects.filter(asset_id=asset_id, state=VersionStateChoice.PUBLISHED, removed_at__isnull=True)
        .order_by("asset_language_id", "-created_at")
        .distinct("asset_language_id")
        .values_list("id", flat=True)
    )


def version_sessions(base_q: Q, period: Period, kinds: Sequence[str]) -> dict[int | None, int]:
    rows = (
        TrafficDaily.objects.filter(base_q, period.daily_q(), kind__in=list(kinds))
        .values("asset_version_id")
        .annotate(v=Sum("sessions"))
        .order_by()
    )
    return {row["asset_version_id"]: int(row["v"] or 0) for row in rows}


def data_updated_at() -> datetime | None:
    """The newest error-free import run (Logpush files or Django events)."""
    return UsageImportState.objects.filter(key__in=[LOGPUSH_JOB, DJANGO_FOLDIN_JOB], last_error="").aggregate(
        latest=Max("last_run_at")
    )["latest"]


# -- listener growth (first seen, cohorts) -------------------------------------------------------


def _listener_events(base_q: Q, start: datetime, end: datetime, kinds: Sequence[str], statuses: Sequence[str]):
    return TrafficEvent.objects.filter(
        base_q, _unique_q(kinds, statuses, "listener_id"), occurred_at__gte=start, occurred_at__lt=end, is_bot=False
    )


def new_listeners(
    base_q: Q, since: date, period: Period, kinds: Sequence[str], statuses: Sequence[str], granularity: str
) -> tuple[int, dict[date, int]]:
    """Listeners first seen (from `since`) before the period, and per bucket inside it."""
    firsts = (
        _listener_events(base_q, day_start(since), day_start(period.end + timedelta(days=1)), kinds, statuses)
        .values("listener_id")
        .annotate(first=Min("occurred_at"))
        .order_by()
    )
    sql, params = firsts.query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT CASE WHEN first < %s THEN NULL ELSE date_trunc(%s, first AT TIME ZONE 'UTC')::date END,
                   COUNT(*)
            FROM ({sql}) firsts
            GROUP BY 1
            """,  # nosec B608 — the subquery is compiled by the ORM; values are parameters
            [day_start(period.start), granularity, *params],
        )
        rows = cursor.fetchall()
    before = sum(count for bucket, count in rows if bucket is None)
    return before, {bucket: count for bucket, count in rows if bucket is not None}


def listener_cohorts(
    base_q: Q, since: date, period: Period, kinds: Sequence[str], statuses: Sequence[str]
) -> list[tuple[date, date, int]]:
    """(cohort week, active week, listeners): cohort = week first seen (from `since`), inside the period."""
    events = _listener_events(
        base_q, day_start(since), day_start(period.end + timedelta(days=1)), kinds, statuses
    ).values("listener_id", "occurred_at")
    sql, params = events.query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            WITH active AS (
                SELECT DISTINCT listener_id, date_trunc('week', occurred_at AT TIME ZONE 'UTC')::date AS week
                FROM ({sql}) events
            ),
            cohorts AS (SELECT listener_id, MIN(week) AS cohort FROM active GROUP BY listener_id)
            SELECT cohorts.cohort, active.week, COUNT(*)
            FROM active JOIN cohorts USING (listener_id)
            WHERE cohorts.cohort >= date_trunc('week', %s::date)::date
            GROUP BY 1, 2
            """,  # nosec B608 — the subquery is compiled by the ORM; values are parameters
            [*params, period.start],
        )
        return list(cursor.fetchall())


def first_seen(
    base_q: Q, since: date, end: date, kinds: Sequence[str], statuses: Sequence[str], dimension: str, limit: int
) -> list[tuple[Any, datetime]]:
    """(raw dimension value, first counted event) from `since`, newest first."""
    column = DIMENSION_COLUMNS[dimension]
    rows = (
        _listener_events(base_q, day_start(since), day_start(end + timedelta(days=1)), kinds, statuses)
        .exclude(**{f"{column}__isnull": True})
        .exclude(**{column: UNKNOWN_COUNTRY} if dimension == "country" else {})
        .values(column)
        .annotate(first=Min("occurred_at"))
        .order_by("-first", column)[:limit]
    )
    return [(row[column], row["first"]) for row in rows]


# -- recitation coverage -------------------------------------------------------------------------


def recitation_coverage(assets: QuerySet) -> list[dict[str, Any]]:
    """Per recitation asset: name, surahs in its default folder, and tracks with / without ayah timings."""
    timed = RecitationAyahTiming.objects.filter(track=OuterRef("pk"))
    tracks = (
        RecitationSurahTrack.objects.filter(asset__in=assets, folder__is_default=True)
        .annotate(timed=Exists(timed))
        .values("asset_id")
        .annotate(
            surahs=ArrayAgg("surah_number", distinct=True, default=Value([])),
            tracks=Count("id"),
            timed_tracks=Count("id", filter=Q(timed=True)),
        )
        .order_by()
    )
    by_asset = {row["asset_id"]: row for row in tracks}
    rows = []
    for asset in assets.values("id", "name").order_by("name", "id"):
        row = by_asset.get(asset["id"], {"surahs": [], "tracks": 0, "timed_tracks": 0})
        rows.append({**asset, **row})
    rows.sort(key=lambda row: (len(row["surahs"]), row["name"], row["id"]))
    return rows


def surah_plays(since: date) -> dict[int, int]:
    """Plays per surah across every recitation since `since` (aggregate only)."""
    rows = (
        TrafficDaily.objects.filter(day__gte=since, kind__in=list(AUDIO_KINDS), surah__isnull=False)
        .values("surah")
        .annotate(v=Sum("sessions"))
        .order_by()
    )
    return {row["surah"]: int(row["v"] or 0) for row in rows}
