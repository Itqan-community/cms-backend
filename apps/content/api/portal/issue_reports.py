import logging
from typing import Annotated, Any, Literal

from django.utils.translation import gettext_lazy as _
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, ContentIssueReport, ContentIssueReportComment
from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.middlewares.publisher_middleware import get_portal_publisher

router = ItqanRouter(tags=[NinjaTag.ISSUE_REPORTS])
logger = logging.getLogger(__name__)


class IssueReportOutReporter(Schema):
    id: int
    name: str
    email: str | None = Field(None, description="Staff only; publisher members reach the reporter through comments")


class IssueReportOut(Schema):
    id: int
    reporter: IssueReportOutReporter
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

    @staticmethod
    def resolve_reporter(obj: ContentIssueReport, context: dict) -> dict[str, Any]:
        """The reporter's address is shown to staff only, so a publisher cannot contact them outside Fanar."""
        request = context["request"]
        reporter = obj.reporter
        return {
            "id": reporter.id,
            "name": reporter.name,
            "email": reporter.email if request.user.is_staff else None,
        }


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
    description: str | None = None
    status: ContentIssueReport.StatusChoice | None = None
    context: dict[str, Any] | None = Field(
        None,
        description=(
            "Omit to keep the context. When sent it must be complete for the asset's category "
            "(see create); null is accepted only for categories that take no location"
        ),
    )


class IssueReportFilter(FilterSchema):
    status: Annotated[list[ContentIssueReport.StatusChoice] | None, FilterLookup(q="status__in")] = None
    reporter_id: Annotated[int | None, FilterLookup(q="reporter_id")] = None


class IssueReportAssetMushafLayoutOut(Schema):
    page_count: int


class IssueReportAssetOut(Schema):
    id: int
    name: str
    category: str
    mushaf_layout: IssueReportAssetMushafLayoutOut | None = None


class IssueReportCommentAuthorOut(Schema):
    id: int
    name: str
    is_reporter: bool = Field(description="True when the reporter wrote the comment")


class IssueReportCommentOut(Schema):
    id: int
    author: IssueReportCommentAuthorOut | None = Field(description="Null when the author's account was deleted")
    body: str
    created_at: AwareDatetime

    @staticmethod
    def resolve_author(obj: ContentIssueReportComment, context: dict) -> dict[str, Any] | None:
        if obj.author is None:
            return None
        return {"id": obj.author.id, "name": obj.author.name, "is_reporter": obj.author_id == obj.report.reporter_id}


class IssueReportCommentIn(Schema):
    body: str = Field(description="1-2000 characters; HTML tags are removed")


def _get_service() -> IssueReportService:
    return IssueReportService(IssueReportRepository())


@router.get("issue-report-assets/", response=list[IssueReportAssetOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name"])
def list_issue_report_assets(request: Request):
    """The assets a report can be filed against from the portal: the selected publisher's (`X-Tenant`).

    Unlike the gallery list, drafts and assets outside the gallery are included.
    """
    return Asset.objects.select_related("mushaf_layout").filter(request.publisher_q()).order_by("name", "id")


@router.post(
    "issue-reports/",
    response={
        201: IssueReportOut,
        400: NinjaErrorResponse[Literal["invalid_issue_context"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
    },
)
def create_issue_report(request: Request, data: IssueReportCreateIn):
    logger.info(f"Creating issue report [asset_id={data.asset_id}, user_id={request.user.id}]")
    service = _get_service()
    # With a publisher selected (X-Tenant) the asset must be that publisher's; a consumer reporting
    # from the gallery sends no tenant and may report any asset.
    portal_publisher = get_portal_publisher(request)
    report = service.create_issue_report(
        reporter=request.user,
        asset_id=data.asset_id,
        description=data.description,
        context=data.context,
        publisher_id=portal_publisher.id if portal_publisher else None,
    )
    logger.info(f"Issue report created [report_id={report.id}, user_id={request.user.id}]")
    return 201, report


@router.get("issue-reports/", response=list[IssueReportOut])
@paginate
@ordering(ordering_fields=["created_at", "status"])
def list_issue_reports(request: Request, filters: IssueReportFilter = Query()):
    return _get_service().get_issue_reports(publisher_q=request.publisher_q(), filters=filters)


@router.get(
    "issue-reports/{report_id}/",
    response={200: IssueReportOut, 404: NinjaErrorResponse[Literal["report_not_found"]]},
)
def get_issue_report(request: Request, report_id: int):
    report = _get_service().get_issue_report(report_id, publisher_q=request.publisher_q())
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
        status=data.status,
        context=data.context,
        update_context="context" in data.model_fields_set,
        publisher_q=request.publisher_q(),
    )
    logger.info(f"Issue report updated [report_id={report_id}, user_id={request.user.id}]")
    return report


@router.delete(
    "issue-reports/{report_id}/",
    response={204: None, 404: NinjaErrorResponse[Literal["report_not_found"]]},
)
def delete_issue_report(request: Request, report_id: int):
    logger.info(f"Deleting issue report [report_id={report_id}, user_id={request.user.id}]")
    _get_service().delete_issue_report(report_id=report_id, user=request.user, publisher_q=request.publisher_q())
    logger.info(f"Issue report deleted [report_id={report_id}, user_id={request.user.id}]")
    return 204, None


@router.get(
    "issue-reports/{report_id}/comments/",
    response={200: list[IssueReportCommentOut], 404: NinjaErrorResponse[Literal["report_not_found"]]},
)
def list_issue_report_comments(request: Request, report_id: int):
    """The report's comment thread, oldest first."""
    report = _get_service().get_issue_report(report_id, publisher_q=request.publisher_q())
    if not report:
        raise ItqanError(error_name="report_not_found", message=_("Issue report not found."), status_code=404)
    comments = list(ContentIssueReportComment.objects.filter(report=report).select_related("author"))
    for comment in comments:
        comment.report = report  # marks the reporter's comments without a join
    return comments


@router.post(
    "issue-reports/{report_id}/comments/",
    response={
        201: IssueReportCommentOut,
        400: NinjaErrorResponse[Literal["comment_empty"]] | NinjaErrorResponse[Literal["comment_too_long"]],
        404: NinjaErrorResponse[Literal["report_not_found"]],
    },
)
def create_issue_report_comment(request: Request, report_id: int, data: IssueReportCommentIn):
    logger.info(f"Adding issue report comment [report_id={report_id}, user_id={request.user.id}]")
    comment = _get_service().add_comment(
        report_id=report_id, author=request.user, body=data.body, publisher_q=request.publisher_q()
    )
    return 201, comment
