from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.html import strip_tags

from apps.content.models import ContentIssueReport
from apps.content.repositories.issue_report import IssueReportRepository

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


class IssueReportService:
    def __init__(self, repo: IssueReportRepository) -> None:
        self.repo = repo

    def create_issue_report(
        self,
        reporter: User,
        content_type: str,
        content_id: int,
        description: str,
    ) -> ContentIssueReport:
        """
        Validate and create a new issue report.
        """
        # 1. Sanitize description
        clean_description = strip_tags(description).strip()

        # 2. Validate description length (redundant with model clean() but good for service layer feedback)
        if len(clean_description) < 10:
            raise ValidationError("Description must be at least 10 characters long.")
        if len(clean_description) > 2000:
            raise ValidationError("Description cannot exceed 2000 characters.")

        # 3. Verify content exists
        content_object = self.repo.get_content_object(content_type, content_id)
        if not content_object:
            raise ValidationError(f"Content object not found: {content_type} with ID {content_id}")

        # 4. Create report via repository
        return self.repo.create_issue_report(
            reporter=reporter,
            content_object=content_object,
            description=clean_description,
            status=ContentIssueReport.StatusChoice.PENDING,
        )

    def get_issue_reports(
        self,
        publisher_q: Q | None = None,
        filters: Any = None,
    ) -> QuerySet[ContentIssueReport]:
        """
        Retrieve issue reports with filtering logic.
        """
        # Convert Pydantic filters to dict if needed
        filters_dict = filters.model_dump(exclude_none=True) if filters and hasattr(filters, "model_dump") else {}

        # Handle custom filters mapping
        # E.g. if we want to support filtering by content_type string in API
        if "content_type" in filters_dict:
            ctype = filters_dict.pop("content_type")
            filters_dict["content_type__model"] = ctype

        # Apply publisher context logic
        q_filter = Q()

        if publisher_q:
            # We filter for reports where:
            # 1. Content is a Resource owned by publisher
            # 2. Content is an Asset whose Resource is owned by publisher

            # We need to import models here to avoid circular imports at module level
            from apps.content.models import Asset, Resource

            # publisher_q typically is Q(publisher=publisher_obj).
            # reliable to apply to Resource model which has 'publisher' field.

            allowed_resource_ids = Resource.objects.filter(publisher_q).values_list("id", flat=True)

            # 1. Resources
            resource_published_q = Q(content_type__model="resource") & Q(object_id__in=allowed_resource_ids)

            # 2. Assets
            # Filter assets belonging to allowed resources
            allowed_asset_ids = Asset.objects.filter(resource__id__in=allowed_resource_ids).values_list("id", flat=True)

            asset_published_q = Q(content_type__model="asset") & Q(object_id__in=allowed_asset_ids)

            # Combine
            q_filter &= resource_published_q | asset_published_q

        return self.repo.list_issue_reports_qs(filters=filters_dict, q_filter=q_filter)

    def update_report_status(
        self, report_id: int, new_status: ContentIssueReport.StatusChoice, user: User
    ) -> ContentIssueReport:
        """
        Update the status of an issue report.
        """
        report = self.repo.get_issue_report_by_id(report_id)
        if not report:
            raise ValidationError(f"Issue report with ID {report_id} not found.")

        # Business logic: validate transition?
        # For now, allow any transition.

        return self.repo.update_issue_report_status(report, new_status)
