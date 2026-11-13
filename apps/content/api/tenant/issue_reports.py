import logging
from typing import Annotated, Any, Literal

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.auth import internal_auth
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ISSUE_REPORTS])
logger = logging.getLogger(__name__)


class IssueReportOut(Schema):
    id: int
    asset_id: int
    asset_name: str
    asset_category: str | None
    description: str
    context: dict[str, Any] | None = Field(
        None, description="Where in the asset the issue is; the shape depends on the asset category"
    )
    context_label: str = Field(description='The context in words, e.g. "Al-Baqarah 2:255"; empty when none')
    status: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IssueReportCreateIn(Schema):
    asset_id: int
    description: str
    context: dict[str, Any] | None = Field(
        None,
        description=(
            "Where in the asset the issue is. Required by category: {surah, ayah} for recitation and text, "
            "{page} for mushaf, {page?, glyph?} with at least one for font; other categories take none "
            "(omit or null)"
        ),
    )


class IssueReportUpdateIn(Schema):
    description: str
    context: dict[str, Any] | None = Field(
        None,
        description=(
            "Omit to keep the context. When sent it must be complete for the asset's category "
            "(see create); null is accepted only for categories that take no location"
        ),
    )


class IssueReportFilter(FilterSchema):
    status: Annotated[list[str] | None, FilterLookup(q="status__in")] = None


def _get_service() -> IssueReportService:
    return IssueReportService(IssueReportRepository())


def _publisher_scope(request: Request) -> Q:
    """The tenant publisher's reports; none at all when the request resolved no tenant domain."""
    return request.publisher_q() if request.publisher else Q(pk__in=[])


@router.post(
    "issue-reports/",
    response={
        201: IssueReportOut,
        400: NinjaErrorResponse[Literal["invalid_issue_context"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
    },
    auth=internal_auth,
)
def create_issue_report(request: Request, data: IssueReportCreateIn):
    logger.info(f"Creating issue report [asset_id={data.asset_id}, user_id={request.user.id}]")
    report = _get_service().create_issue_report(
        reporter=request.user,
        asset_id=data.asset_id,
        description=data.description,
        context=data.context,
    )
    logger.info(f"Issue report created [report_id={report.id}, user_id={request.user.id}]")
    return 201, report


@router.get("issue-reports/", response=list[IssueReportOut])
@paginate
@ordering(ordering_fields=["created_at", "status"])
def list_issue_reports(request: Request, filters: IssueReportFilter = Query()):
    return _get_service().get_issue_reports(
        publisher_q=_publisher_scope(request),
        filters=filters,
    )


@router.get(
    "issue-reports/{report_id}/",
    response={200: IssueReportOut, 404: NinjaErrorResponse[Literal["report_not_found"]]},
)
def get_issue_report(request: Request, report_id: int):
    report = _get_service().get_issue_report(report_id, publisher_q=_publisher_scope(request))
    if not report:
        raise ItqanError(error_name="report_not_found", message=_("Issue report not found."), status_code=404)
    return report


@router.patch(
    "issue-reports/{report_id}/",
    response={
        200: IssueReportOut,
        400: NinjaErrorResponse[Literal["invalid_issue_context"]],
        404: NinjaErrorResponse[Literal["report_not_found"]],
    },
)
def update_issue_report(request: Request, report_id: int, data: IssueReportUpdateIn):
    logger.info(f"Updating issue report [report_id={report_id}, user_id={request.user.id}]")
    report = _get_service().update_issue_report(
        report_id=report_id,
        user=request.user,
        description=data.description,
        publisher_q=_publisher_scope(request),
        context=data.context,
        update_context="context" in data.model_fields_set,
    )
    logger.info(f"Issue report updated [report_id={report_id}, user_id={request.user.id}]")
    return report


@router.delete(
    "issue-reports/{report_id}/",
    response={204: None, 404: NinjaErrorResponse[Literal["report_not_found"]]},
    auth=internal_auth,
)
def delete_issue_report(request: Request, report_id: int):
    logger.info(f"Deleting issue report [report_id={report_id}, user_id={request.user.id}]")
    _get_service().delete_issue_report(report_id=report_id, user=request.user, publisher_q=_publisher_scope(request))
    logger.info(f"Issue report deleted [report_id={report_id}, user_id={request.user.id}]")
    return 204, None
