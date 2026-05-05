import logging
from typing import Annotated, Literal

from django.http import Http404
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import NinjaErrorResponse
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
    description: str
    status: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IssueReportCreateIn(Schema):
    asset_id: int
    description: str


class IssueReportUpdateIn(Schema):
    description: str


class IssueReportFilter(FilterSchema):
    status: Annotated[list[str] | None, FilterLookup(q="status__in")] = None


def _get_service() -> IssueReportService:
    return IssueReportService(IssueReportRepository())


@router.post("issue-reports/", response={201: IssueReportOut}, auth=ninja_jwt_auth)
def create_issue_report(request: Request, data: IssueReportCreateIn):
    logger.info(f"Creating issue report [asset_id={data.asset_id}, user_id={request.user.id}]")
    report = _get_service().create_issue_report(
        reporter=request.user,
        asset_id=data.asset_id,
        description=data.description,
    )
    logger.info(f"Issue report created [report_id={report.id}, user_id={request.user.id}]")
    return 201, report


@router.get("issue-reports/", response=list[IssueReportOut])
@paginate
@ordering(ordering_fields=["created_at", "status"])
def list_issue_reports(request: Request, filters: IssueReportFilter = Query()):
    return _get_service().get_issue_reports(
        publisher_q=request.publisher_q(),
        filters=filters,
    )


@router.get(
    "issue-reports/{report_id}/",
    response={200: IssueReportOut, 404: NinjaErrorResponse[Literal["report_not_found"]]},
    auth=ninja_jwt_auth,
)
def get_issue_report(request: Request, report_id: int):
    report = _get_service().get_issue_report(report_id)
    if not report:
        raise Http404("Issue report not found.")
    return report


@router.patch(
    "issue-reports/{report_id}/",
    response={200: IssueReportOut, 404: NinjaErrorResponse[Literal["report_not_found"]]},
    auth=ninja_jwt_auth,
)
def update_issue_report(request: Request, report_id: int, data: IssueReportUpdateIn):
    logger.info(f"Updating issue report [report_id={report_id}, user_id={request.user.id}]")
    report = _get_service().update_issue_report(
        report_id=report_id,
        user=request.user,
        description=data.description,
    )
    logger.info(f"Issue report updated [report_id={report_id}, user_id={request.user.id}]")
    return report


@router.delete(
    "issue-reports/{report_id}/",
    response={204: None, 404: NinjaErrorResponse[Literal["report_not_found"]]},
    auth=ninja_jwt_auth,
)
def delete_issue_report(request: Request, report_id: int):
    logger.info(f"Deleting issue report [report_id={report_id}, user_id={request.user.id}]")
    _get_service().delete_issue_report(report_id=report_id, user=request.user)
    logger.info(f"Issue report deleted [report_id={report_id}, user_id={request.user.id}]")
    return 204, None
