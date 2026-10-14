"""Portal endpoints: asset download statistics for the publisher in the request.

Portal reads query the models directly (repo rule). All buckets are UTC.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from django.db.models import F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils.translation import gettext_lazy as _
from ninja import Field, Query, Schema
from pydantic import AwareDatetime

from apps.content.models import Asset
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
    UsageSyncState,
)
from apps.usage_tracking.repositories.asset_downloads import SYNC_KEY

router = ItqanRouter(tags=[NinjaTag.USAGE])

_MAX_HOURLY_DAYS = 31
# Bounds the zero-filled series size (one point per day) and the scanned rows.
_MAX_RANGE_DAYS = 3660
# Leaves room for the "end of day" / "next month" arithmetic without overflowing `date.max`.
_LATEST_END_DATE = date(9999, 11, 30)

# Annotation names avoid clashing with the model's own `requests` / `bytes` / `plays` fields.
_METRIC_ANNOTATIONS: dict[str, Any] = {
    "m_full": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.FULL)), 0),
    "m_partial": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.PARTIAL)), 0),
    "m_other": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.OTHER)), 0),
    "m_bytes": Coalesce(Sum("bytes"), 0),
    "m_plays": Coalesce(Sum("plays"), 0),
}
_ZERO = {"m_full": 0, "m_partial": 0, "m_other": 0, "m_bytes": 0, "m_plays": 0}

_ERRORS = {
    400: NinjaErrorResponse[Literal["invalid_range"]] | NinjaErrorResponse[Literal["range_too_large"]],
    403: NinjaErrorResponse[Literal["permission_denied"]],
    404: NinjaErrorResponse[Literal["asset_not_found"]],
}


class MetricsOut(Schema):
    requests_full: int
    requests_partial: int
    requests_other: int
    bytes: int
    plays: int


class SummaryOut(Schema):
    data_until: AwareDatetime | None
    total: MetricsOut
    by_file_kind: dict[str, MetricsOut]


class PointOut(MetricsOut):
    t: str


class SeriesOut(Schema):
    key: str
    points: list[PointOut]


class TimeseriesOut(Schema):
    data_until: AwareDatetime | None
    granularity: str
    series: list[SeriesOut]


class BreakdownItemOut(MetricsOut):
    key: str
    label: str | None


class BreakdownOut(Schema):
    data_until: AwareDatetime | None
    by: str
    items: list[BreakdownItemOut]


class StatsQuery(Schema):
    start_date: date
    end_date: date
    asset_id: int | None = None
    file_kind: AssetDownloadFileKind | None = None


class TimeseriesQuery(StatsQuery):
    granularity: Literal["hour", "day", "month"] = "day"
    split_by: Literal["file_kind", "status_class"] | None = None


class BreakdownQuery(StatsQuery):
    by: Literal["asset", "surah", "country"]
    limit: int = Field(10, ge=1, le=100)


def _metrics(row: dict[str, Any]) -> dict[str, int]:
    return {
        "requests_full": row["m_full"],
        "requests_partial": row["m_partial"],
        "requests_other": row["m_other"],
        "bytes": row["m_bytes"],
        "plays": row["m_plays"],
    }


def _data_until() -> datetime | None:
    return UsageSyncState.objects.filter(key=SYNC_KEY).values_list("watermark", flat=True).first()


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _scoped(request: Request, params: StatsQuery, model: type[AssetDownloadDaily | AssetDownloadHourly]) -> QuerySet:
    if params.end_date < params.start_date:
        raise ItqanError("invalid_range", _("The end date must not be before the start date."), 400)
    if (params.end_date - params.start_date).days + 1 > _MAX_RANGE_DAYS:
        raise ItqanError(
            "range_too_large",
            _("Statistics are limited to {days} days per request.").format(days=_MAX_RANGE_DAYS),
            400,
        )
    if params.end_date > _LATEST_END_DATE:
        raise ItqanError("invalid_range", _("The end date is out of the supported range."), 400)
    assets = Asset.objects.filter(request.publisher_q())
    if params.asset_id is not None:
        if not assets.filter(id=params.asset_id).exists():
            raise ItqanError("asset_not_found", _("Asset does not exist."), 404)
        queryset = model.objects.filter(asset_id=params.asset_id)
    else:
        queryset = model.objects.filter(asset_id__in=assets.values("id"))
    if params.file_kind:
        queryset = queryset.filter(file_kind=params.file_kind)
    if model is AssetDownloadHourly:
        end = _day_start(params.end_date) + timedelta(days=1)
        return queryset.filter(hour__gte=_day_start(params.start_date), hour__lt=end)
    return queryset.filter(day__gte=params.start_date, day__lte=params.end_date)


def _buckets(params: TimeseriesQuery) -> list[date | datetime]:
    if params.granularity == "hour":
        start = _day_start(params.start_date)
        hours = ((params.end_date - params.start_date).days + 1) * 24
        return [start + timedelta(hours=offset) for offset in range(hours)]
    if params.granularity == "day":
        days = (params.end_date - params.start_date).days + 1
        return [params.start_date + timedelta(days=offset) for offset in range(days)]
    months: list[date | datetime] = []
    current = params.start_date.replace(day=1)
    while current <= params.end_date:
        months.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return months


@router.get(
    "usage/downloads/summary/",
    response={200: SummaryOut, **_ERRORS},
    description="Download totals for the publisher's assets, per file kind (UTC days, inclusive).",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_summary(request: Request, params: StatsQuery = Query(...)):
    queryset = _scoped(request, params, AssetDownloadDaily)
    per_kind = {row["file_kind"]: row for row in queryset.values("file_kind").annotate(**_METRIC_ANNOTATIONS)}
    return {
        "data_until": _data_until(),
        "total": _metrics(queryset.aggregate(**_METRIC_ANNOTATIONS)),
        "by_file_kind": {kind: _metrics(per_kind.get(kind, _ZERO)) for kind in AssetDownloadFileKind.values},
    }


@router.get(
    "usage/downloads/timeseries/",
    response={200: TimeseriesOut, **_ERRORS},
    description="Zero-filled download series (hour granularity limited to 31 days).",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_timeseries(request: Request, params: TimeseriesQuery = Query(...)):
    if params.granularity == "hour":
        if (params.end_date - params.start_date).days + 1 > _MAX_HOURLY_DAYS:
            raise ItqanError(
                "range_too_large",
                _("Hourly statistics are limited to {days} days.").format(days=_MAX_HOURLY_DAYS),
                400,
            )
        queryset = _scoped(request, params, AssetDownloadHourly)
        bucket: Any = F("hour")
    else:
        queryset = _scoped(request, params, AssetDownloadDaily)
        bucket = TruncMonth("day") if params.granularity == "month" else F("day")

    group_by = ["bucket", params.split_by] if params.split_by else ["bucket"]
    rows = queryset.annotate(bucket=bucket).values(*group_by).annotate(**_METRIC_ANNOTATIONS)
    by_key: dict[tuple[str, Any], dict[str, Any]] = {
        (row[params.split_by] if params.split_by else "all", row["bucket"]): row for row in rows
    }
    if params.split_by == "file_kind":
        keys = [params.file_kind] if params.file_kind else list(AssetDownloadFileKind.values)
    elif params.split_by == "status_class":
        keys = list(AssetDownloadStatusClass.values)
    else:
        keys = ["all"]
    buckets = _buckets(params)
    return {
        "data_until": _data_until(),
        "granularity": params.granularity,
        "series": [
            {
                "key": key,
                "points": [
                    {"t": moment.isoformat(), **_metrics(by_key.get((key, moment), _ZERO))} for moment in buckets
                ],
            }
            for key in keys
        ],
    }


@router.get(
    "usage/downloads/breakdown/",
    response={200: BreakdownOut, **_ERRORS},
    description="Top assets, surahs or countries by plays.",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_breakdown(request: Request, params: BreakdownQuery = Query(...)):
    field = {"asset": "asset_id", "surah": "surah", "country": "country"}[params.by]
    queryset = _scoped(request, params, AssetDownloadDaily)
    if params.by == "surah":
        queryset = queryset.filter(surah__isnull=False)
    rows = list(
        queryset.values(field).annotate(**_METRIC_ANNOTATIONS).order_by("-m_plays", "-m_full", field)[: params.limit]
    )
    labels: dict[Any, str] = {}
    if params.by == "asset":
        labels = dict(Asset.objects.filter(id__in=[row[field] for row in rows]).values_list("id", "name"))
    return {
        "data_until": _data_until(),
        "by": params.by,
        "items": [{"key": str(row[field]), "label": labels.get(row[field]), **_metrics(row)} for row in rows],
    }
