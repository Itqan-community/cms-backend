"""Issue reports on a publisher's own website: visitors can file a report, nothing more.

Reading and handling reports happens in the portal, by the publisher's members; a tenant
domain never shows existing reports.
"""

import logging
from typing import Any, Literal

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.auth import internal_auth
from apps.core.ninja_utils.errors import NinjaErrorResponse
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


def _get_service() -> IssueReportService:
    return IssueReportService(IssueReportRepository())


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
