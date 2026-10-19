"""Itqan admin usage reports: every publisher (or one, with `publisher_id`), staff only.

Includes traffic that belongs to no asset (API lists and search), the publisher leaderboard
and the unseen-traffic reconciliation against R2 reads.
"""

from ninja import Query
from rest_framework.exceptions import PermissionDenied

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.api.usage_schemas import (
    REPORT_ERRORS,
    AdminBreakdownQuery,
    AdminScopeQuery,
    AdminTimeseriesQuery,
    BreakdownOut,
    ExportQuery,
    LeaderboardQuery,
    ReconciliationOut,
    ReconciliationQuery,
    ReportQuery,
    SummaryOut,
    TimeseriesOut,
)
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.usage_reports import ReportScope

router = ItqanRouter(tags=[NinjaTag.USAGE])


def _scope(request: Request, publisher_id: int | None) -> ReportScope:
    if not request.user.is_staff:
        raise PermissionDenied
    return usage_reports.admin_scope(publisher_id)


@router.get(
    "admin/usage/summary/",
    response={200: SummaryOut, **REPORT_ERRORS},
    description="Headline usage numbers across every publisher (Itqan staff).",
)
def admin_usage_summary(request: Request, params: ReportQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.summary(_scope(request, scope.publisher_id), params.filters())


@router.get(
    "admin/usage/timeseries/",
    response={200: TimeseriesOut, **REPORT_ERRORS},
    description="A zero-filled series across every publisher; can also be split by publisher (Itqan staff).",
)
def admin_usage_timeseries(
    request: Request, params: AdminTimeseriesQuery = Query(...), scope: AdminScopeQuery = Query(...)
):
    return usage_reports.timeseries(
        _scope(request, scope.publisher_id),
        params.filters(),
        metric=params.metric,
        granularity=params.granularity,
        split_by=params.split_by,
        top=params.top,
        compare=params.compare is not None,
    )


@router.get(
    "admin/usage/breakdown/",
    response={200: BreakdownOut, **REPORT_ERRORS},
    description="One metric per dimension across every publisher; can also break down by publisher (Itqan staff).",
)
def admin_usage_breakdown(
    request: Request, params: AdminBreakdownQuery = Query(...), scope: AdminScopeQuery = Query(...)
):
    return usage_reports.breakdown(
        _scope(request, scope.publisher_id),
        params.filters(),
        metric=params.metric,
        by=params.by,
        limit=params.limit,
        compare=params.compare is not None,
        tz=params.tz,
    )


@router.get(
    "admin/usage/leaderboard/",
    response={200: BreakdownOut, **REPORT_ERRORS},
    description="Top publishers or assets by a metric, with their previous-period values (Itqan staff).",
)
def admin_usage_leaderboard(
    request: Request, params: LeaderboardQuery = Query(...), scope: AdminScopeQuery = Query(...)
):
    return usage_reports.breakdown(
        _scope(request, scope.publisher_id),
        params.filters(),
        metric=params.metric,
        by=params.by,
        limit=params.limit,
        compare=True,
    )


@router.get(
    "admin/usage/reconciliation/",
    response={200: ReconciliationOut, **REPORT_ERRORS},
    description="Unseen traffic: R2 reads minus the edge requests seen for the same objects (Itqan staff).",
)
def admin_usage_reconciliation(request: Request, params: ReconciliationQuery = Query(...)):
    return usage_reports.reconciliation(
        _scope(request, params.publisher_id), params.start_date, params.end_date, params.limit
    )


@router.get(
    "admin/usage/export/",
    response=REPORT_ERRORS,
    description="CSV of the additive metrics per period, asset and publisher (Itqan staff).",
)
def admin_usage_export(request: Request, params: ExportQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.export_csv(_scope(request, scope.publisher_id), params.filters(), params.granularity)
