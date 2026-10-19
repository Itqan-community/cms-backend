"""Portal usage reports for the publisher in the request (`PORTAL_READ_USAGE`).

The views build the caller's scope and hand it to the shared report engine
(`services/usage_reports.py`), which also serves the admin and developer scopes.
"""

from ninja import Query

from apps.content.models import Asset
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.publishers.models import Publisher
from apps.usage_tracking.api.usage_schemas import (
    REPORT_ERRORS,
    BreakdownOut,
    BreakdownQuery,
    ExportQuery,
    ReportQuery,
    SummaryOut,
    TimeseriesOut,
    TimeseriesQuery,
)
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.usage_reports import ReportScope

router = ItqanRouter(tags=[NinjaTag.USAGE])

_READ_USAGE = [permission_class(PermissionChoice.PORTAL_READ_USAGE)]


def _scope(request: Request) -> ReportScope:
    """The publishers the caller may report on: the X-Tenant one, else all of their memberships."""
    if request.user.is_staff and request.publisher is None:
        return usage_reports.publisher_scope(Asset.objects.all(), None)
    publisher_ids = tuple(Publisher.objects.filter(request.publisher_q("id")).values_list("id", flat=True))
    return usage_reports.publisher_scope(Asset.objects.filter(publisher_id__in=publisher_ids), publisher_ids)


@router.get(
    "usage/summary/",
    response={200: SummaryOut, **REPORT_ERRORS},
    description="Headline usage numbers with previous-period changes, metric definitions and disclaimers.",
)
@permission_required(_READ_USAGE)
def usage_summary(request: Request, params: ReportQuery = Query(...)):
    return usage_reports.summary(_scope(request), params.filters())


@router.get(
    "usage/timeseries/",
    response={200: TimeseriesOut, **REPORT_ERRORS},
    description="A zero-filled series of one metric, optionally split by a dimension (top N + other).",
)
@permission_required(_READ_USAGE)
def usage_timeseries(request: Request, params: TimeseriesQuery = Query(...)):
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
    "usage/breakdown/",
    response={200: BreakdownOut, **REPORT_ERRORS},
    description="One metric per asset, surah, country, channel, platform, app, version, language or hour of week.",
)
@permission_required(_READ_USAGE)
def usage_breakdown(request: Request, params: BreakdownQuery = Query(...)):
    return usage_reports.breakdown(
        _scope(request),
        params.filters(),
        metric=params.metric,
        by=params.by,
        limit=params.limit,
        compare=params.compare is not None,
        tz=params.tz,
    )


@router.get(
    "usage/export/",
    response=REPORT_ERRORS,
    description="CSV of plays, downloads, installs, API calls, views, requests and bytes per period and asset.",
)
@permission_required(_READ_USAGE)
def usage_export(request: Request, params: ExportQuery = Query(...)):
    return usage_reports.export_csv(_scope(request), params.filters(), params.granularity)
