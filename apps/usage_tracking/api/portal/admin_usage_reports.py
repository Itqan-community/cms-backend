"""Itqan admin usage reports: every publisher (or one, with `publisher_id`), staff only.

Includes traffic that belongs to no asset (API lists and search), the publisher leaderboard
and the unseen-traffic reconciliation against R2 reads.
"""

from typing import Literal

from ninja import Query
from rest_framework.exceptions import PermissionDenied

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.api.usage_schemas import (
    COVERAGE_ERRORS,
    LISTENER_ERRORS,
    REPORT_ERRORS,
    SEARCH_TERMS_ERRORS,
    AdminBreakdownQuery,
    AdminScopeQuery,
    AdminTimeseriesQuery,
    BreakdownOut,
    CohortsOut,
    CoverageOut,
    CoverageQuery,
    ExportQuery,
    FirstSeenOut,
    FirstSeenQuery,
    LeaderboardQuery,
    ListenersOut,
    ListenersQuery,
    ReconciliationOut,
    ReconciliationQuery,
    ReportQuery,
    SearchTermsOut,
    SearchTermsQuery,
    SummaryOut,
    TimeseriesOut,
)
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.usage_reports import ReportScope

router = ItqanRouter(tags=[NinjaTag.USAGE])

_DENIED = {403: NinjaErrorResponse[Literal["permission_denied"]]}
ADMIN_ERRORS = {**REPORT_ERRORS, **_DENIED}


def _scope(request: Request, publisher_id: int | None) -> ReportScope:
    if not request.user.is_staff:
        raise PermissionDenied
    return usage_reports.admin_scope(publisher_id)


@router.get(
    "admin/usage/summary/",
    response={200: SummaryOut, **ADMIN_ERRORS},
    description="Headline usage numbers across every publisher (Itqan staff).",
)
def admin_usage_summary(request: Request, params: ReportQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.summary(_scope(request, scope.publisher_id), params.filters())


@router.get(
    "admin/usage/timeseries/",
    response={200: TimeseriesOut, **ADMIN_ERRORS},
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
    response={200: BreakdownOut, **ADMIN_ERRORS},
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
        order=params.order,
    )


@router.get(
    "admin/usage/leaderboard/",
    response={200: BreakdownOut, **ADMIN_ERRORS},
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
    response={200: ReconciliationOut, **ADMIN_ERRORS},
    description="Unseen traffic: R2 reads minus the edge requests seen for the same objects (Itqan staff).",
)
def admin_usage_reconciliation(request: Request, params: ReconciliationQuery = Query(...)):
    return usage_reports.reconciliation(
        _scope(request, params.publisher_id), params.start_date, params.end_date, params.limit
    )


@router.get(
    "admin/usage/export/",
    response=ADMIN_ERRORS,
    description="CSV of the additive metrics per period, asset and publisher (Itqan staff).",
)
def admin_usage_export(request: Request, params: ExportQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.export_csv(_scope(request, scope.publisher_id), params.filters(), params.granularity)


@router.get(
    "admin/usage/listeners/",
    response={200: ListenersOut, **LISTENER_ERRORS, **_DENIED},
    description="New, returning and cumulative listeners across every publisher (Itqan staff).",
)
def admin_usage_listeners(request: Request, params: ListenersQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.listeners(
        _scope(request, scope.publisher_id), params.filters(), granularity=params.granularity
    )


@router.get(
    "admin/usage/cohorts/",
    response={200: CohortsOut, **LISTENER_ERRORS, **_DENIED},
    description="Weekly listener cohorts across every publisher (Itqan staff).",
)
def admin_usage_cohorts(request: Request, params: ReportQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.cohorts(_scope(request, scope.publisher_id), params.filters())


@router.get(
    "admin/usage/first-seen/",
    response={200: FirstSeenOut, **LISTENER_ERRORS, **_DENIED},
    description="When each country or app first played content, across every publisher (Itqan staff).",
)
def admin_usage_first_seen(request: Request, params: FirstSeenQuery = Query(...), scope: AdminScopeQuery = Query(...)):
    return usage_reports.first_seen(
        _scope(request, scope.publisher_id), params.filters(), by=params.by, limit=params.limit
    )


@router.get(
    "admin/usage/search-terms/",
    response={200: SearchTermsOut, **SEARCH_TERMS_ERRORS, **_DENIED},
    description="Top gallery search terms, matched to reciters, riwayat and qira'at (Itqan staff).",
)
def admin_usage_search_terms(request: Request, params: SearchTermsQuery = Query(...)):
    _scope(request, None)
    return usage_reports.search_terms(
        params.start_date, params.end_date, zero_results=params.zero_results, limit=params.limit
    )


@router.get(
    "admin/usage/recitation-coverage/",
    response={200: CoverageOut, **COVERAGE_ERRORS, **_DENIED},
    description="Recitations missing surahs across every publisher, or one with `publisher_id` (Itqan staff).",
)
def admin_usage_recitation_coverage(
    request: Request, params: CoverageQuery = Query(...), scope: AdminScopeQuery = Query(...)
):
    return usage_reports.recitation_coverage(_scope(request, scope.publisher_id), **params.dict())
