from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Q

from apps.content.models import Asset, ContentIssueReport

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


class IssueReportRepository:
    def get_asset_by_id(self, asset_id: int) -> Asset | None:
        return Asset.objects.filter(id=asset_id).first()

    def create_issue_report(
        self,
        reporter: User,
        asset: Asset,
        description: str,
        status: ContentIssueReport.StatusChoice = ContentIssueReport.StatusChoice.PENDING,
    ) -> ContentIssueReport:
        return ContentIssueReport.objects.create(
            reporter=reporter,
            asset=asset,
            description=description,
            status=status,
        )

    def list_issue_reports_qs(
        self, filters: dict[str, Any] | None = None, q_filter: Q | None = None
    ) -> QuerySet[ContentIssueReport]:
        qs = ContentIssueReport.objects.select_related("reporter", "asset").order_by("-created_at")

        if filters:
            qs = qs.filter(**filters)

        if q_filter:
            qs = qs.filter(q_filter)

        return qs

    def get_issue_report_by_id(self, report_id: int) -> ContentIssueReport | None:
        try:
            return ContentIssueReport.objects.select_related("reporter", "asset").get(id=report_id)
        except ContentIssueReport.DoesNotExist:
            return None

    def update_issue_report(
        self,
        report: ContentIssueReport,
        description: str | None = None,
        status: ContentIssueReport.StatusChoice | None = None,
    ) -> ContentIssueReport:
        update_fields = ["updated_at"]
        if description is not None:
            report.description = description
            update_fields.append("description")
        if status is not None:
            report.status = status
            update_fields.append("status")
        report.save(update_fields=update_fields)
        return report

    def delete_issue_report(self, report: ContentIssueReport) -> None:
        report.delete()
