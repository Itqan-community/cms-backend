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

from django.db.models import Count, F, Max, OuterRef, Q, QuerySet, Subquery, Sum, Value
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

from apps.content.models import PUBLISHED_VERSION_CATEGORIES, Asset, AssetLanguage, AssetVersion, VersionStateChoice
from apps.publishers.models import Publisher
from apps.usage_tracking.models import (
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

# Report dimension -> rollup/event column. `publisher` and `hour_of_week` are computed.
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
COMPUTED_DIMENSIONS = ("publisher", "hour_of_week")

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
    if dimension == "publisher":
        publisher = Asset.objects.filter(pk=OuterRef("asset_id")).values("publisher_id")[:1]
        return queryset.annotate(d_publisher=Subquery(publisher)), ["d_publisher"]
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
        "reads": Coalesce(Sum("reads"), 0),
        "edge": Coalesce(Sum("edge_requests"), 0),
        "unseen": Coalesce(Sum(_UNSEEN), 0),
    }
    total = queryset.aggregate(**metrics)
    assets = list(queryset.values("asset_id").annotate(**metrics).order_by("-unseen", "asset_id")[:limit])
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
    return {}


def asset_publishers(asset_ids: Iterable[int]) -> dict[int, tuple[str, int | None, str]]:
    """Asset id -> (name, publisher id, publisher name)."""
    return {
        row["id"]: (row["name"], row["publisher_id"], row["publisher__name"] or "")
        for row in Asset.objects.filter(id__in=[i for i in asset_ids if i is not None]).values(
            "id", "name", "publisher_id", "publisher__name"
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
