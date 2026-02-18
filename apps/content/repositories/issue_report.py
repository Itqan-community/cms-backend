from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from django.db.models import Q

from apps.content.models import Asset, ContentIssueReport, Resource

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


class IssueReportRepository:
    def create_issue_report(
        self,
        reporter: User,
        content_object: Resource | Asset,
        description: str,
        status: ContentIssueReport.StatusChoice = ContentIssueReport.StatusChoice.PENDING,
    ) -> ContentIssueReport:
        """
        Create a new content issue report.
        """
        return ContentIssueReport.objects.create(
            reporter=reporter,
            content_object=content_object,
            description=description,
            status=status,
        )

    def list_issue_reports_qs(
        self, filters: dict[str, Any] | None = None, q_filter: Q | None = None
    ) -> QuerySet[ContentIssueReport]:
        """
        Return a queryset of issue reports filtered by criteria.
        Expects filters dictionary to contain ready-to-use Django filter arguments.
        Optionally accepts a Q object for complex queries.
        """
        qs = ContentIssueReport.objects.select_related("reporter", "content_type").order_by("-created_at")

        if filters:
            qs = qs.filter(**filters)

        if q_filter:
            qs = qs.filter(q_filter)

        return qs

    def get_issue_report_by_id(self, report_id: int) -> ContentIssueReport | None:
        """
        Retrieve a single issue report by ID.
        """
        try:
            return ContentIssueReport.objects.select_related("reporter", "content_type").get(id=report_id)
        except ContentIssueReport.DoesNotExist:
            return None

    def update_issue_report_status(
        self, report: ContentIssueReport, status: ContentIssueReport.StatusChoice
    ) -> ContentIssueReport:
        """
        Update the status of an issue report.
        """
        report.status = status
        report.save(update_fields=["status", "updated_at"])
        return report

    def get_content_object(
        self, content_type: Literal["resource", "asset"], content_id: int
    ) -> Resource | Asset | None:
        """
        Helper validation method to retrieve the content object (Resource or Asset).
        """
        if content_type == "resource":
            return Resource.objects.filter(id=content_id).first()
        elif content_type == "asset":
            return Asset.objects.filter(id=content_id).first()
        return None
