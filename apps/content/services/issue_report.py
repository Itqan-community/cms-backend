from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.db.models import Q
from django.utils.html import strip_tags
from django.utils.translation import gettext as _

from apps.content.models import ContentIssueReport
from apps.content.repositories.issue_report import IssueReportRepository
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


class IssueReportService:
    def __init__(self, repo: IssueReportRepository) -> None:
        self.repo = repo

    def create_issue_report(
        self,
        reporter: User,
        asset_id: int,
        description: str,
    ) -> ContentIssueReport:
        clean_description = strip_tags(description).strip()

        if len(clean_description) < 10:
            raise ItqanError(
                error_name="description_too_short",
                message=_("Description must be at least 10 characters long."),
                status_code=400,
            )
        if len(clean_description) > 2000:
            raise ItqanError(
                error_name="description_too_long",
                message=_("Description cannot exceed 2000 characters."),
                status_code=400,
            )

        asset = self.repo.get_asset_by_id(asset_id)
        if not asset:
            raise ItqanError(
                error_name="asset_not_found",
                message=_("Asset with ID {asset_id} not found.").format(asset_id=asset_id),
                status_code=404,
            )

        report = self.repo.create_issue_report(
            reporter=reporter,
            asset=asset,
            description=clean_description,
            status=ContentIssueReport.StatusChoice.PENDING,
        )
        logger.info(f"Issue report created [report_id={report.pk}, reporter_id={reporter.pk}, asset_id={asset_id}]")
        return report

    def get_issue_reports(
        self,
        publisher_q: Q | None = None,
        filters: Any = None,
    ) -> QuerySet[ContentIssueReport]:
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}

        if "status" in filters_dict:
            filters_dict["status__in"] = filters_dict.pop("status")

        q_filter = Q()

        if publisher_q:
            from apps.content.models import Asset

            q_filter &= Q(asset__in=Asset.objects.filter(publisher_q))

        return self.repo.list_issue_reports_qs(filters=filters_dict, q_filter=q_filter)

    def get_issue_report(self, report_id: int) -> ContentIssueReport | None:
        return self.repo.get_issue_report_by_id(report_id)

    def update_issue_report(
        self,
        report_id: int,
        user: User,
        description: str | None = None,
        status: ContentIssueReport.StatusChoice | None = None,
    ) -> ContentIssueReport:
        report = self.repo.get_issue_report_by_id(report_id)
        if not report:
            raise ItqanError(
                error_name="report_not_found",
                message=_("Issue report with ID {report_id} not found.").format(report_id=report_id),
                status_code=404,
            )

        if not user.is_staff:
            if report.reporter_id != user.pk:
                raise ItqanError(
                    error_name="permission_denied",
                    message=_("You can only update your own issue reports."),
                    status_code=403,
                )
            if report.status != ContentIssueReport.StatusChoice.PENDING:
                raise ItqanError(
                    error_name="report_not_editable",
                    message=_("You can only update pending issue reports."),
                    status_code=403,
                )
            status = None  # reporters cannot change status

        if description is not None:
            clean_description = strip_tags(description).strip()
            if len(clean_description) < 10:
                raise ItqanError(
                    error_name="description_too_short",
                    message=_("Description must be at least 10 characters long."),
                    status_code=400,
                )
            if len(clean_description) > 2000:
                raise ItqanError(
                    error_name="description_too_long",
                    message=_("Description cannot exceed 2000 characters."),
                    status_code=400,
                )
            description = clean_description

        old_status = report.status
        updated = self.repo.update_issue_report(report, description=description, status=status)
        logger.info(f"Issue report updated [report_id={report_id}, updated_by={user.pk}]")

        if status is not None and status != old_status:
            from apps.content.tasks import send_issue_status_update_email

            send_issue_status_update_email.delay(report_id, old_status, status)

        return updated

    def delete_issue_report(self, report_id: int, user: User) -> None:
        report = self.repo.get_issue_report_by_id(report_id)
        if not report:
            raise ItqanError(
                error_name="report_not_found",
                message=_("Issue report with ID {report_id} not found.").format(report_id=report_id),
                status_code=404,
            )

        if not user.is_staff:
            if report.reporter_id != user.pk:
                raise ItqanError(
                    error_name="permission_denied",
                    message=_("You can only delete your own issue reports."),
                    status_code=403,
                )
            if report.status != ContentIssueReport.StatusChoice.PENDING:
                raise ItqanError(
                    error_name="report_not_editable",
                    message=_("You can only delete pending issue reports."),
                    status_code=403,
                )

        self.repo.delete_issue_report(report)
        logger.info(f"Issue report deleted [report_id={report_id}, deleted_by={user.pk}]")
