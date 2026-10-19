"""Usage reports: one engine behind the publisher, admin, developer and public report scopes.

Additive metrics (plays, downloads, requests, ...) read the hourly/daily rollups; unique
metrics read traffic events, or the monthly uniques once the range reaches past retention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.usage_tracking.models import (
    AUDIO_KINDS,
    COUNTED_STATUSES,
    SESSION_STATUSES,
    TrafficKind,
    UniqueMeasure,
)

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
