"""Request and response schemas shared by every usage report scope (portal, admin, developer)."""

from datetime import date
from typing import Literal

from ninja import Field, Schema
from pydantic import AwareDatetime

from apps.content.models import CategoryChoice
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.usage_tracking.models import TrafficChannel, TrafficKind, TrafficPlatform
from apps.usage_tracking.services.usage_reports import Granularity, Metric, ReportFilters

SplitDimension = Literal[
    "asset", "surah", "country", "channel", "platform", "app", "version", "language", "kind", "endpoint"
]
BreakdownDimension = Literal[
    "asset", "surah", "country", "channel", "platform", "app", "version", "language", "kind", "endpoint", "hour_of_week"
]
AdminSplitDimension = SplitDimension | Literal["publisher"]
AdminBreakdownDimension = BreakdownDimension | Literal["publisher"]

REPORT_ERRORS = {
    400: NinjaErrorResponse[Literal["invalid_range"]]
    | NinjaErrorResponse[Literal["range_too_large"]]
    | NinjaErrorResponse[Literal["invalid_metric_for_kind"]]
    | NinjaErrorResponse[Literal["invalid_dimension"]]
    | NinjaErrorResponse[Literal["invalid_timezone"]],
    404: NinjaErrorResponse[Literal["asset_not_found"]] | NinjaErrorResponse[Literal["app_not_found"]],
}


class ReportQuery(Schema):
    start_date: date = Field(..., description="First UTC day, inclusive.")
    end_date: date = Field(..., description="Last UTC day, inclusive (ranges up to 3660 days).")
    asset_id: int | None = None
    category: CategoryChoice | None = None
    kind: TrafficKind | None = None
    channel: TrafficChannel | None = None
    platform: TrafficPlatform | None = None
    app: int | None = Field(None, description="Integrating app id (as returned by breakdowns by app).")
    country: str | None = Field(None, min_length=2, max_length=2, description="ISO country code.")
    language: str | None = Field(None, max_length=10)
    version_id: int | None = None
    surah: int | None = Field(None, ge=1, le=114)

    def filters(self) -> ReportFilters:
        return ReportFilters(
            start_date=self.start_date,
            end_date=self.end_date,
            asset_id=self.asset_id,
            category=self.category.value if self.category else None,
            kind=self.kind.value if self.kind else None,
            channel=self.channel.value if self.channel else None,
            platform=self.platform.value if self.platform else None,
            app=self.app,
            country=self.country.upper() if self.country else None,
            language=self.language or None,
            version_id=self.version_id,
            surah=self.surah,
        )


class TimeseriesQuery(ReportQuery):
    metric: Metric = "plays"
    granularity: Granularity = Field("day", description="`hour` is limited to 31 days.")
    split_by: SplitDimension | None = None
    top: int = Field(8, ge=1, le=20, description="Series kept when splitting; the rest are summed into `other`.")
    compare: Literal["previous_period"] | None = None


class AdminTimeseriesQuery(TimeseriesQuery):
    split_by: AdminSplitDimension | None = None  # type: ignore[assignment]


class BreakdownQuery(ReportQuery):
    metric: Metric = "plays"
    by: BreakdownDimension
    limit: int = Field(10, ge=1, le=200)
    compare: Literal["previous_period"] | None = None
    tz: str = Field("UTC", max_length=64, description="IANA time zone, used by `by=hour_of_week` only.")


class AdminBreakdownQuery(BreakdownQuery):
    by: AdminBreakdownDimension  # type: ignore[assignment]


class AdminScopeQuery(Schema):
    publisher_id: int | None = Field(None, description="Limit the report to one publisher's assets.")


class LeaderboardQuery(ReportQuery):
    metric: Metric = "plays"
    by: Literal["publisher", "asset"] = "publisher"
    limit: int = Field(20, ge=1, le=200)


class ReconciliationQuery(Schema):
    start_date: date
    end_date: date
    publisher_id: int | None = None
    limit: int = Field(20, ge=1, le=200)


class ReconciliationNumbersOut(Schema):
    reads: int = Field(..., description="R2 GetObject reads.")
    edge_requests: int = Field(..., description="Edge requests seen in Logpush for the same objects.")
    unseen: int = Field(..., description="Reads the edge never saw: max(reads − edge requests, 0) per object-hour.")


class ReconciliationAssetOut(ReconciliationNumbersOut):
    key: str
    label: str | None


class ReconciliationDayOut(ReconciliationNumbersOut):
    t: str


class ReconciliationOut(Schema):
    total: ReconciliationNumbersOut
    assets: list[ReconciliationAssetOut]
    days: list[ReconciliationDayOut]
    data_updated_at: AwareDatetime | None


class ExportQuery(ReportQuery):
    granularity: Granularity = "day"


class PeriodOut(Schema):
    start_date: date
    end_date: date


class MetricValueOut(Schema):
    value: int | None = Field(..., description="Null when it cannot be computed (see `uniques_basis`).")
    previous: int | None
    change: float | None = Field(..., description="(value − previous) ÷ previous; null when previous is 0.")


class DisclaimerOut(Schema):
    code: str
    text: str


class SummaryOut(Schema):
    period: PeriodOut
    previous_period: PeriodOut
    metrics: dict[str, MetricValueOut]
    integrating_apps: MetricValueOut
    unidentified_apps: bool = Field(..., description="Some plays, downloads or API calls came from unidentified apps.")
    latest_version_share: float | None = Field(
        ..., description="Share of downloads and installs on the current version (asset_id only)."
    )
    uniques_basis: Literal["events", "monthly", "unavailable"]
    definitions: dict[str, str]
    disclaimers: list[DisclaimerOut]
    data_updated_at: AwareDatetime | None


class PointOut(Schema):
    t: str
    value: int | None


class SeriesOut(Schema):
    key: str
    label: str | None
    points: list[PointOut]


class TimeseriesOut(Schema):
    metric: str
    granularity: str
    series: list[SeriesOut]
    previous: list[PointOut] | None
    data_updated_at: AwareDatetime | None


class BreakdownItemOut(Schema):
    key: str = Field(..., description='Dimension value; hour_of_week keys are "<ISO weekday>-<hour>".')
    label: str | None
    value: int | str = Field(..., description='"<3" where the privacy floor hides a small number.')
    previous: int | None


class BreakdownOut(Schema):
    metric: str
    by: str
    items: list[BreakdownItemOut]
    other: int | None
    total: int | None
    data_updated_at: AwareDatetime | None


class PublicUsageCountsOut(Schema):
    plays: int = Field(..., description="All-time plays, floored to two significant figures.")
    downloads: int = Field(..., description="All-time downloads and CLI installs, floored to two significant figures.")
    apps: int = Field(..., description="Identified apps with at least one play, download or API call.")
    disclaimers: list[DisclaimerOut]
    data_updated_at: AwareDatetime | None
