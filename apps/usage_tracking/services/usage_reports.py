"""Usage reports: one engine behind the publisher, admin, developer and public report scopes.

Additive metrics (plays, downloads, requests, ...) read the hourly/daily rollups; unique
metrics read traffic events, or the monthly uniques once the range reaches past retention.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import csv
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, QuerySet
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.utils.translation import get_language, gettext_lazy as _

from apps.content.models import Asset
from apps.core.ninja_utils.errors import ItqanError
from apps.usage_tracking.models import (
    AUDIO_KINDS,
    COUNTED_STATUSES,
    SESSION_STATUSES,
    TrafficChannel,
    TrafficKind,
    UniqueMeasure,
    UniqueScope,
)
from apps.usage_tracking.repositories import usage_reports as repo
from apps.usage_tracking.repositories.usage_reports import Period

Metric = Literal[
    "plays",
    "downloads",
    "installs",
    "api_calls",
    "requests",
    "bytes",
    "unique_listeners",
    "unique_downloaders",
    "unique_end_users",
    "views",
]
Granularity = Literal["hour", "day", "week", "month"]

MAX_RANGE_DAYS = 3660
MAX_HOURLY_DAYS = 31
EARLIEST_START_DATE = date(2000, 1, 1)
# Leaves room for "end of day" / "next month" arithmetic without overflowing `date.max`.
LATEST_END_DATE = date(9999, 11, 30)

DOWNLOAD_KINDS: tuple[str, ...] = (TrafficKind.VERSION_FILE, TrafficKind.GALLERY_DOWNLOAD)


@dataclass(frozen=True, slots=True)
class RollupMetric:
    field: str  # TrafficHourly/TrafficDaily column summed
    kinds: tuple[str, ...] | None  # None: every kind


@dataclass(frozen=True, slots=True)
class UniqueMetric:
    kinds: tuple[str, ...]
    statuses: tuple[str, ...]
    identity: str  # TrafficEvent column counted distinct
    measure: str  # TrafficMonthlyUniques.measure


ROLLUP_METRICS: dict[str, RollupMetric] = {
    "plays": RollupMetric("sessions", tuple(AUDIO_KINDS)),
    "downloads": RollupMetric("sessions", DOWNLOAD_KINDS),
    "installs": RollupMetric("sessions", (TrafficKind.CLI_INSTALL,)),
    "api_calls": RollupMetric("sessions", (TrafficKind.API_CALL,)),
    "views": RollupMetric("sessions", (TrafficKind.VIEW,)),
    "requests": RollupMetric("requests", None),
    "bytes": RollupMetric("bytes", None),
}
UNIQUE_METRICS: dict[str, UniqueMetric] = {
    "unique_listeners": UniqueMetric(
        tuple(AUDIO_KINDS), tuple(SESSION_STATUSES), "listener_id", UniqueMeasure.LISTENERS
    ),
    "unique_downloaders": UniqueMetric(
        DOWNLOAD_KINDS, tuple(SESSION_STATUSES), "listener_id", UniqueMeasure.DOWNLOADERS
    ),
    "unique_end_users": UniqueMetric(
        (TrafficKind.API_CALL,), tuple(COUNTED_STATUSES), "end_user_id", UniqueMeasure.END_USERS
    ),
}

METRIC_DEFINITIONS = {
    "plays": _(
        "A listener's first request for an audio file after at least 5 minutes without one. "
        "Seeking and buffering inside a play are not counted again."
    ),
    "downloads": _("Version files and gallery downloads, counted like plays: repeats within 5 minutes count once."),
    "installs": _("Packages installed with the itqan CLI, once per installation, version and day."),
    "api_calls": _("Successful public API calls for this content, including responses served from the CDN cache."),
    "views": _("Asset pages opened by signed-in users in the gallery."),
    "requests": _("Every successful request for an asset file or API route, including partial requests."),
    "bytes": _("Bytes delivered to clients."),
    "unique_listeners": _("Distinct devices and networks that played audio in the period (estimate)."),
    "unique_downloaders": _("Distinct devices and networks that downloaded files in the period (estimate)."),
    "unique_end_users": _("Distinct end users reported by apps through the X-External-User-Id header."),
}

DISCLAIMERS = {
    "lower_bound": _(
        "Counts are lower bounds: apps and browsers cache files locally and some content is re-hosted, "
        "so that usage never reaches Itqan."
    ),
    "uniques_estimated": _(
        "Unique counts are estimates: people sharing a network may count as one, "
        "and one person on several networks may count more than once."
    ),
    "hourly_delay": _("Reports are updated hourly; the latest hours may still be incomplete."),
}


@dataclass(frozen=True, slots=True)
class ReportFilters:
    start_date: date
    end_date: date
    asset_id: int | None = None
    category: str | None = None
    kind: str | None = None
    channel: str | None = None
    platform: str | None = None
    app: int | None = None
    country: str | None = None
    language: str | None = None
    version_id: int | None = None
    surah: int | None = None


def range_days(start: date, end: date) -> int:
    return (end - start).days + 1


def validate_filters(filters: ReportFilters, *, granularity: str = "day") -> None:
    if filters.end_date < filters.start_date:
        raise ItqanError("invalid_range", _("The end date must not be before the start date."), 400)
    if filters.start_date < EARLIEST_START_DATE or filters.end_date > LATEST_END_DATE:
        raise ItqanError("invalid_range", _("The dates are out of the supported range."), 400)
    days = range_days(filters.start_date, filters.end_date)
    if days > MAX_RANGE_DAYS:
        raise ItqanError(
            "range_too_large",
            _("Reports are limited to {days} days per request.").format(days=MAX_RANGE_DAYS),
            400,
        )
    if granularity == "hour" and days > MAX_HOURLY_DAYS:
        raise ItqanError(
            "range_too_large",
            _("Hourly reports are limited to {days} days.").format(days=MAX_HOURLY_DAYS),
            400,
        )


def metric_kinds(metric: str) -> tuple[str, ...] | None:
    if metric in UNIQUE_METRICS:
        return UNIQUE_METRICS[metric].kinds
    return ROLLUP_METRICS[metric].kinds


def check_metric_kind(metric: str, filters: ReportFilters) -> None:
    kinds = metric_kinds(metric)
    if filters.kind and kinds is not None and filters.kind not in kinds:
        raise ItqanError(
            "invalid_metric_for_kind",
            _("The metric {metric} does not apply to {kind} traffic.").format(metric=metric, kind=filters.kind),
            400,
        )


def previous_period(start: date, end: date) -> tuple[date, date]:
    length = timedelta(days=range_days(start, end))
    return start - length, end - length


def parse_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ItqanError("invalid_timezone", _("Unknown time zone."), 400) from None


# ---------------------------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------------------------

SPLIT_DIMENSIONS = frozenset(repo.DIMENSION_COLUMNS)
BREAKDOWN_DIMENSIONS = SPLIT_DIMENSIONS | {"hour_of_week"}
ADMIN_DIMENSIONS = BREAKDOWN_DIMENSIONS | {"publisher"}
PRIVACY_FLOOR = 3
# Kinds whose sessions make an app "integrating" (spec §8).
APP_KINDS: tuple[str, ...] = (*AUDIO_KINDS, *DOWNLOAD_KINDS, TrafficKind.API_CALL)


@dataclass(frozen=True)
class ReportScope:
    """Who is asking and what they may see."""

    name: str  # "publisher" | "admin" | "developer"
    cache_key: str
    assets: QuerySet | None = None  # visible assets (None: every row, assigned to an asset or not)
    app_ids: tuple[int, ...] | None = None  # visible apps (None: any)
    publisher_ids: tuple[int, ...] | None = None  # for monthly uniques (None: all publishers)
    privacy_floor: bool = False
    dimensions: frozenset[str] = field(default=BREAKDOWN_DIMENSIONS)

    def q(self) -> Q:
        q = Q()
        if self.assets is not None:
            q &= Q(asset_id__in=self.assets.values("id"))
        if self.app_ids is not None:
            q &= Q(app_id__in=list(self.app_ids))
        return q


def admin_scope(publisher_id: int | None) -> ReportScope:
    if publisher_id is None:
        return ReportScope(name="admin", cache_key="all", dimensions=ADMIN_DIMENSIONS)
    return ReportScope(
        name="admin",
        cache_key=f"publisher:{publisher_id}",
        assets=Asset.objects.filter(publisher_id=publisher_id),
        publisher_ids=(publisher_id,),
        dimensions=ADMIN_DIMENSIONS,
    )


def publisher_scope(assets: QuerySet, publisher_ids: tuple[int, ...] | None) -> ReportScope:
    """`publisher_ids=None` means every publisher (Itqan staff without `X-Tenant`)."""
    key = "all" if publisher_ids is None else ",".join(map(str, sorted(publisher_ids)))
    return ReportScope(name="publisher", cache_key=key, assets=assets, publisher_ids=publisher_ids)


def developer_scope(user_id: int, app_ids: tuple[int, ...]) -> ReportScope:
    return ReportScope(
        name="developer",
        cache_key=f"user:{user_id}:{','.join(map(str, sorted(app_ids)))}",
        app_ids=app_ids,
        privacy_floor=True,
    )


# ---------------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------------


def cache_seconds() -> int:
    return settings.USAGE_REPORTS_CACHE_SECONDS


def cached(namespace: str, identity: list[Any], compute: Callable[[], Any], seconds: int | None = None) -> Any:
    """Cache `compute()` under every value that shapes the response, including the language."""
    seconds = cache_seconds() if seconds is None else seconds
    if seconds <= 0:
        return compute()
    raw = json.dumps([namespace, get_language(), identity], default=str, sort_keys=True)
    key = f"usage-report:v1:{namespace}:{hashlib.sha256(raw.encode()).hexdigest()}"
    value = cache.get(key)
    if value is None:
        value = compute()
        cache.set(key, value, seconds)
    return value


def _cached(scope: ReportScope, report: str, params: dict[str, Any], compute: Callable[[], Any]) -> Any:
    return cached(report, [scope.name, scope.cache_key, params], compute)


def retention_cutoff(today: date | None = None) -> date:
    """First day still kept in `TrafficEvent` (the nightly purge keeps whole months)."""
    month = (today or datetime.now(UTC).date()).replace(day=1)
    years, index = divmod(month.month - 1 - settings.USAGE_EVENT_RETENTION_MONTHS, 12)
    return date(month.year + years, index + 1, 1)


def _filters_q(filters: ReportFilters) -> Q:
    q = Q()
    if filters.asset_id is not None:
        q &= Q(asset_id=filters.asset_id)
    if filters.category:
        q &= Q(asset_id__in=Asset.objects.filter(category=filters.category).values("id"))
    for value, column in (
        (filters.kind, "kind"),
        (filters.channel, "channel"),
        (filters.platform, "platform"),
        (filters.app, "app_id"),
        (filters.country, "country"),
        (filters.language, "language"),
        (filters.version_id, "asset_version_id"),
        (filters.surah, "surah"),
    ):
        if value is not None and value != "":
            q &= Q(**{column: value})
    return q


def _base_q(scope: ReportScope, filters: ReportFilters) -> Q:
    return scope.q() & _filters_q(filters)


def check_scope(scope: ReportScope, filters: ReportFilters) -> str | None:
    """Reject filters outside the scope; returns the filtered asset's category, if any."""
    category = None
    if filters.asset_id is not None:
        assets = scope.assets if scope.assets is not None else Asset.objects.all()
        category = assets.filter(id=filters.asset_id).values_list("category", flat=True).first()
        if category is None and scope.assets is not None:
            raise ItqanError("asset_not_found", _("Asset does not exist."), 404)
    if filters.app is not None and scope.app_ids is not None and filters.app not in scope.app_ids:
        raise ItqanError("app_not_found", _("App does not exist."), 404)
    return category


def check_dimension(scope: ReportScope, dimension: str | None, allowed: frozenset[str]) -> None:
    if dimension is not None and (dimension not in allowed or dimension not in scope.dimensions):
        raise ItqanError("invalid_dimension", _("This report cannot be split by {name}.").format(name=dimension), 400)


def _change(value: int | None, previous: int | None) -> float | None:
    if value is None or not previous:
        return None
    return round((value - previous) / previous, 4)


def _unique_spec(metric: str) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    spec = UNIQUE_METRICS[metric]
    return spec.kinds, spec.statuses, spec.identity


def _monthly_scope(scope: ReportScope, filters: ReportFilters) -> tuple[str, tuple[int, ...] | None] | None:
    """The stored monthly-uniques scope matching these filters, or None when none matches."""
    others = asdict(filters)
    for name in ("start_date", "end_date", "asset_id", "app"):
        others.pop(name)
    if any(value not in (None, "") for value in others.values()):
        return None
    if filters.asset_id is not None:
        return UniqueScope.ASSET, (filters.asset_id,)
    if filters.app is not None:
        return UniqueScope.APP, (filters.app,)
    if scope.app_ids is not None:
        return UniqueScope.APP, scope.app_ids
    if scope.publisher_ids is not None:
        return UniqueScope.PUBLISHER, scope.publisher_ids
    if scope.assets is not None:
        return None
    return UniqueScope.ALL, (0,)


def _period_uniques(
    scope: ReportScope, filters: ReportFilters, base_q: Q, periods: dict[str, Period]
) -> tuple[dict[str, dict[str, int | None]], dict[str, str]]:
    """Unique metrics per period, and how each period was counted."""
    cutoff = retention_cutoff()
    exact = {name: period for name, period in periods.items() if period.start >= cutoff}
    specs = {metric: _unique_spec(metric) for metric in UNIQUE_METRICS}
    values: dict[str, dict[str, int | None]] = dict(repo.unique_totals(base_q, exact, specs))
    basis = dict.fromkeys(exact, "events")
    monthly = _monthly_scope(scope, filters)
    for name, period in periods.items():
        if name in exact:
            continue
        if monthly is None:
            values[name] = dict.fromkeys(UNIQUE_METRICS)
            basis[name] = "unavailable"
            continue
        values[name] = {
            metric: sum(repo.monthly_uniques(*monthly, spec.measure, period.start, period.end).values())
            for metric, spec in UNIQUE_METRICS.items()
        }
        basis[name] = "monthly"
    return values, basis


def disclaimers() -> list[dict[str, str]]:
    return [{"code": code, "text": str(text)} for code, text in DISCLAIMERS.items()]


def _labels(dimension: str, keys: list[str]) -> dict[str, str]:
    if dimension not in ("asset", "app", "publisher", "version"):
        return {}
    raw = [int(key) for key in keys if key.isdigit()]
    return {str(key): label for key, label in repo.labels(dimension, raw).items()}


# ---------------------------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------------------------


def summary(scope: ReportScope, filters: ReportFilters) -> dict[str, Any]:
    validate_filters(filters)
    category = check_scope(scope, filters)

    def compute() -> dict[str, Any]:
        base_q = _base_q(scope, filters)
        previous = Period(*previous_period(filters.start_date, filters.end_date))
        periods = {"current": Period(filters.start_date, filters.end_date), "previous": previous}
        totals = repo.rollup_totals(
            base_q,
            periods,
            {metric: (spec.field, spec.kinds) for metric, spec in ROLLUP_METRICS.items()},
            APP_KINDS,
            TrafficChannel.APP_UNIDENTIFIED,
        )
        uniques, basis = _period_uniques(scope, filters, base_q, periods)
        metrics = {}
        for metric in METRIC_DEFINITIONS:
            source = uniques if metric in UNIQUE_METRICS else totals
            value, before = source["current"].get(metric), source["previous"].get(metric)
            metrics[metric] = {"value": value, "previous": before, "change": _change(value, before)}
        apps_now, apps_before = totals["current"]["apps"], totals["previous"]["apps"]
        return {
            "period": {"start_date": filters.start_date, "end_date": filters.end_date},
            "previous_period": {"start_date": previous.start, "end_date": previous.end},
            "metrics": metrics,
            "integrating_apps": {"value": apps_now, "previous": apps_before, "change": _change(apps_now, apps_before)},
            "unidentified_apps": totals["current"]["unidentified"] > 0,
            "latest_version_share": _latest_version_share(base_q, filters, category),
            "uniques_basis": basis["current"],
            "definitions": {metric: str(text) for metric, text in METRIC_DEFINITIONS.items()},
            "disclaimers": disclaimers(),
            "data_updated_at": repo.data_updated_at(),
        }

    return _cached(scope, "summary", asdict(filters), compute)


def _latest_version_share(base_q: Q, filters: ReportFilters, category: str | None) -> float | None:
    """Share of downloads + installs on the versions consumers are served now (one asset only)."""
    if filters.asset_id is None or category is None:
        return None
    latest = repo.latest_version_ids(filters.asset_id, category)
    sessions = repo.version_sessions(
        base_q, Period(filters.start_date, filters.end_date), (*DOWNLOAD_KINDS, TrafficKind.CLI_INSTALL)
    )
    total = sum(value for version, value in sessions.items() if version is not None)
    if not total:
        return None
    return round(sum(value for version, value in sessions.items() if version in latest) / total, 4)


# ---------------------------------------------------------------------------------------------
# Timeseries
# ---------------------------------------------------------------------------------------------

Bucket = date | datetime


def bucket_starts(start: date, end: date, granularity: str) -> list[Bucket]:
    if granularity == "hour":
        first = repo.day_start(start)
        return [first + timedelta(hours=offset) for offset in range(range_days(start, end) * 24)]
    if granularity == "day":
        return [start + timedelta(days=offset) for offset in range(range_days(start, end))]
    buckets: list[Bucket] = []
    if granularity == "week":
        current = start - timedelta(days=start.weekday())
        while current <= end:
            buckets.append(current)
            current += timedelta(days=7)
        return buckets
    current = start.replace(day=1)
    while current <= end:
        buckets.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return buckets


def _points(buckets: list[Bucket], values: dict[Any, int | None]) -> list[dict[str, Any]]:
    return [{"t": bucket.isoformat(), "value": values.get(bucket, 0)} for bucket in buckets]


def _bucket_day(bucket: Bucket) -> date:
    return bucket.date() if isinstance(bucket, datetime) else bucket


def _total_values(
    scope: ReportScope,
    filters: ReportFilters,
    base_q: Q,
    metric: str,
    granularity: str,
    period: Period,
    buckets: list[Bucket],
) -> dict[Any, int | None]:
    if metric not in UNIQUE_METRICS:
        spec = ROLLUP_METRICS[metric]
        rows = repo.rollup_series(base_q, period, spec.field, spec.kinds, granularity, None)
        return {bucket: value for bucket, _key, value in rows}
    # Unique metrics: exact distincts inside retention; monthly uniques (month buckets) or None before.
    cutoff = retention_cutoff()
    values: dict[Any, int | None] = {}
    if period.end >= cutoff:
        exact = Period(max(period.start, cutoff), period.end)
        for bucket, _key, value in repo.unique_series(base_q, exact, _unique_spec(metric), granularity):
            values[bucket] = value
    old = [bucket for bucket in buckets if _bucket_day(bucket) < cutoff]
    if old:
        monthly = _monthly_scope(scope, filters) if granularity == "month" else None
        stored = (
            repo.monthly_uniques(*monthly, UNIQUE_METRICS[metric].measure, period.start, period.end) if monthly else {}
        )
        for bucket in old:
            values[bucket] = stored.get(bucket, 0) if monthly else None
    return values


def _split_series(
    base_q: Q,
    metric: str,
    granularity: str,
    split_by: str,
    top: int,
    period: Period,
    buckets: list[Bucket],
) -> list[dict[str, Any]]:
    """Top-N keys by range total, plus "other" (a true distinct over the rest for unique metrics)."""
    by_key: dict[str, dict[Any, int]] = defaultdict(dict)
    if metric in UNIQUE_METRICS:
        spec = _unique_spec(metric)
        groups = repo.unique_groups(base_q, period, spec, split_by, UTC)
        ranked = sorted(groups, key=lambda key: (-groups[key][1], key))
        top_keys, has_rest = ranked[:top], len(ranked) > top
        raw_top = [groups[key][0] for key in top_keys]
        for bucket, key, value in repo.unique_series(base_q, period, spec, granularity, split_by, only_keys=raw_top):
            by_key[key][bucket] = value
        if has_rest:
            for bucket, _key, value in repo.unique_series(
                base_q, period, spec, granularity, split_by, exclude_keys=raw_top, group=False
            ):
                by_key["other"][bucket] = value
    else:
        rollup = ROLLUP_METRICS[metric]
        rows = repo.rollup_series(base_q, period, rollup.field, rollup.kinds, granularity, split_by)
        totals: dict[str, int] = defaultdict(int)
        for _bucket, key, value in rows:
            totals[key] += value
        ranked = sorted(totals, key=lambda key: (-totals[key], key))
        top_keys, has_rest = ranked[:top], len(ranked) > top
        kept = set(top_keys)
        for bucket, key, value in rows:
            target = key if key in kept else "other"
            by_key[target][bucket] = by_key[target].get(bucket, 0) + value
    keys = top_keys + (["other"] if has_rest else [])
    label_map = _labels(split_by, top_keys)
    return [{"key": key, "label": label_map.get(key), "points": _points(buckets, by_key.get(key, {}))} for key in keys]


def timeseries(
    scope: ReportScope,
    filters: ReportFilters,
    *,
    metric: str,
    granularity: str = "day",
    split_by: str | None = None,
    top: int = 8,
    compare: bool = False,
) -> dict[str, Any]:
    validate_filters(filters, granularity=granularity)
    check_metric_kind(metric, filters)
    check_dimension(scope, split_by, scope.dimensions - {"hour_of_week"})
    check_scope(scope, filters)

    def compute() -> dict[str, Any]:
        base_q = _base_q(scope, filters)
        period = Period(filters.start_date, filters.end_date)
        buckets = bucket_starts(period.start, period.end, granularity)
        if split_by:
            series = _split_series(base_q, metric, granularity, split_by, top, period, buckets)
        else:
            values = _total_values(scope, filters, base_q, metric, granularity, period, buckets)
            series = [{"key": "all", "label": None, "points": _points(buckets, values)}]
        previous = None
        if compare:
            before = Period(*previous_period(period.start, period.end))
            before_buckets = bucket_starts(before.start, before.end, granularity)
            previous = _points(
                before_buckets, _total_values(scope, filters, base_q, metric, granularity, before, before_buckets)
            )
        return {
            "metric": metric,
            "granularity": granularity,
            "series": series,
            "previous": previous,
            "data_updated_at": repo.data_updated_at(),
        }

    params = {**asdict(filters), "metric": metric, "g": granularity, "split": split_by, "top": top, "cmp": compare}
    return _cached(scope, "timeseries", params, compute)


# ---------------------------------------------------------------------------------------------
# Breakdown
# ---------------------------------------------------------------------------------------------


def _groups(
    base_q: Q,
    period: Period,
    metric: str,
    by: str,
    zone: ZoneInfo,
    limit: int | None = None,
    only_keys: list[Any] | None = None,
) -> dict[str, tuple[Any, int]]:
    if metric in UNIQUE_METRICS:
        return repo.unique_groups(base_q, period, _unique_spec(metric), by, zone, limit=limit, only_keys=only_keys)
    spec = ROLLUP_METRICS[metric]
    groups = repo.rollup_groups(base_q, period, spec.field, spec.kinds, by, zone)
    if only_keys is not None:
        wanted = set(only_keys)
        groups = {key: value for key, value in groups.items() if value[0] in wanted}
    return groups


def breakdown(
    scope: ReportScope,
    filters: ReportFilters,
    *,
    metric: str,
    by: str,
    limit: int = 10,
    compare: bool = False,
    tz: str = "UTC",
) -> dict[str, Any]:
    validate_filters(filters)
    check_metric_kind(metric, filters)
    check_dimension(scope, by, scope.dimensions)
    zone = parse_tz(tz)
    check_scope(scope, filters)

    def compute() -> dict[str, Any]:
        base_q = _base_q(scope, filters)
        period = Period(filters.start_date, filters.end_date)
        is_unique = metric in UNIQUE_METRICS
        groups = _groups(base_q, period, metric, by, zone, limit=limit if is_unique and by != "hour_of_week" else None)
        if by == "hour_of_week":
            ranked = sorted(groups, key=lambda key: tuple(int(part) for part in key.split("-")))
        else:
            ranked = sorted(groups, key=lambda key: (-groups[key][1], key))[:limit]
        before: dict[str, tuple[Any, int]] = {}
        if compare and ranked:
            before = _groups(
                base_q,
                Period(*previous_period(period.start, period.end)),
                metric,
                by,
                zone,
                only_keys=[groups[key][0] for key in ranked],
            )
        total = None if is_unique else sum(value for _raw, value in groups.values())
        other = None
        if total is not None and by != "hour_of_week":
            other = total - sum(groups[key][1] for key in ranked)
        label_map = _labels(by, ranked)
        items: list[dict[str, Any]] = [
            {
                "key": key,
                "label": label_map.get(key),
                "value": groups[key][1],
                "previous": before.get(key, (None, 0))[1] if compare else None,
            }
            for key in ranked
        ]
        if scope.privacy_floor:
            listeners = repo.listeners_per_group(base_q, period, metric_kinds(metric), by, zone)
            for item in items:
                if listeners.get(item["key"], 0) < PRIVACY_FLOOR:
                    item["value"] = f"<{PRIVACY_FLOOR}"
                    item["previous"] = None
            other = None
        return {
            "metric": metric,
            "by": by,
            "items": items,
            "other": other,
            "total": total,
            "data_updated_at": repo.data_updated_at(),
        }

    params = {**asdict(filters), "metric": metric, "by": by, "limit": limit, "cmp": compare, "tz": tz}
    return _cached(scope, "breakdown", params, compute)


# ---------------------------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------------------------

EXPORT_METRICS = ("plays", "downloads", "installs", "api_calls", "views", "requests", "bytes")


def export_csv(scope: ReportScope, filters: ReportFilters, granularity: str = "day") -> HttpResponse:
    """Additive metrics per period and asset; unique metrics are not additive and are left out."""
    validate_filters(filters, granularity=granularity)
    check_scope(scope, filters)
    rows = repo.export_rows(
        _base_q(scope, filters),
        Period(filters.start_date, filters.end_date),
        granularity,
        {metric: (ROLLUP_METRICS[metric].field, ROLLUP_METRICS[metric].kinds) for metric in EXPORT_METRICS},
    )
    details = repo.asset_details(row["asset_id"] for row in rows)
    with_publisher = scope.name == "admin"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(
        as_attachment=True, filename=f"usage-{filters.start_date}-{filters.end_date}.csv"
    )
    writer = csv.writer(response)
    header = ["period", "asset_id", "asset", "category"]
    if with_publisher:
        header += ["publisher_id", "publisher"]
    writer.writerow(header + list(EXPORT_METRICS))
    for row in rows:
        asset = details.get(row["asset_id"], {})
        line = [row["bucket"].isoformat(), row["asset_id"] or "", asset.get("name", ""), asset.get("category", "")]
        if with_publisher:
            line += [asset.get("publisher_id") or "", asset.get("publisher__name") or ""]
        writer.writerow(line + [row[f"m_{metric}"] for metric in EXPORT_METRICS])
    return response
