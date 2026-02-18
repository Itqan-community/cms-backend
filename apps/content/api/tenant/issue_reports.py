from typing import Literal

from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ISSUE_REPORTS])


class IssueReportOut(Schema):
    id: int
    object_id: int
    content_object_summary: str
    description: str
    status: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IssueReportCreateIn(Schema):
    content_type: Literal["resource", "asset"]
    content_id: int
    description: str


class IssueReportFilter(FilterSchema):
    status: list[str] | None = Field(None, q="status__in")
    content_type: Literal["resource", "asset"] | None = None


@router.post("issue-reports/", response={201: IssueReportOut}, auth=ninja_jwt_auth)
def create_issue_report(request: Request, data: IssueReportCreateIn):

    service = IssueReportService(IssueReportRepository())
    report = service.create_issue_report(
        reporter=request.user,
        content_type=data.content_type,
        content_id=data.content_id,
        description=data.description,
    )
    return 201, report


@router.get("issue-reports/", response=list[IssueReportOut])
@paginate
@ordering(ordering_fields=["created_at", "status"])
def list_issue_reports(request: Request, filters: IssueReportFilter = Query()):
    service = IssueReportService(IssueReportRepository())
    return service.get_issue_reports(
        publisher_q=request.publisher_q(),  # Apply tenant filtering
        filters=filters,
    )
