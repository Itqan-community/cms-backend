"""Developer usage reports: traffic of the signed-in user's apps (one app per API key).

Breakdown rows with fewer than three distinct listeners are returned as "<3".
"""

from ninja import Query

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.api.usage_schemas import (
    REPORT_ERRORS,
    BreakdownOut,
    BreakdownQuery,
    ReportQuery,
    SummaryOut,
    TimeseriesOut,
    TimeseriesQuery,
)
from apps.usage_tracking.models import UsageApp
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.usage_reports import ReportScope

router = ItqanRouter(tags=[NinjaTag.USAGE])


def _scope(request: Request) -> ReportScope:
    app_ids = tuple(UsageApp.objects.filter(user=request.user).values_list("id", flat=True))
    return usage_reports.developer_scope(request.user.id, app_ids)


@router.get(
    "developers/usage/summary/",
    response={200: SummaryOut, **REPORT_ERRORS},
    description="Headline usage of the caller's apps, with previous-period changes and disclaimers.",
)
def developer_usage_summary(request: Request, params: ReportQuery = Query(...)):
    return usage_reports.summary(_scope(request), params.filters())


@router.get(
    "developers/usage/timeseries/",
    response={200: TimeseriesOut, **REPORT_ERRORS},
    description="A zero-filled series of one metric for the caller's apps.",
)
def developer_usage_timeseries(request: Request, params: TimeseriesQuery = Query(...)):
    return usage_reports.timeseries(
        _scope(request),
        params.filters(),
        metric=params.metric,
        granularity=params.granularity,
        split_by=params.split_by,
        top=params.top,
        compare=params.compare is not None,
    )


@router.get(
    "developers/usage/breakdown/",
    response={200: BreakdownOut, **REPORT_ERRORS},
    description='One metric per app, asset, endpoint or other dimension; rows under 3 listeners show "<3".',
)
def developer_usage_breakdown(request: Request, params: BreakdownQuery = Query(...)):
    return usage_reports.breakdown(
        _scope(request),
        params.filters(),
        metric=params.metric,
        by=params.by,
        limit=params.limit,
        compare=params.compare is not None,
        tz=params.tz,
    )
