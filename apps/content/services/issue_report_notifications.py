from __future__ import annotations

import logging

from django.conf import settings

from apps.content.models import ContentIssueReport
from apps.core.services.email import email_service

logger = logging.getLogger(__name__)


class IssueReportNotificationService:
    def notify_status_changed(self, report_id: int, old_status: str, new_status: str) -> None:
        try:
            report = ContentIssueReport.objects.select_related("reporter", "asset").get(pk=report_id)
        except ContentIssueReport.DoesNotExist:
            logger.warning(f"ContentIssueReport not found, skipping email [report_id={report_id}]")
            return

        reporter_email = report.reporter.email
        if not reporter_email:
            logger.warning(f"Reporter has no email, skipping [report_id={report_id}]")
            return

        old_label = ContentIssueReport.StatusChoice(old_status).label
        new_label = ContentIssueReport.StatusChoice(new_status).label
        asset_name = report.asset.name if report.asset else f"Issue #{report_id}"
        portal_base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
        issue_url = f"{portal_base}/issues/{report_id}"

        email_service.send_email(
            subject=f"Your issue status has been updated: {old_label} → {new_label}",
            recipients=[reporter_email],
            template="emails/issue_status_update.html",
            context={
                "report_id": report_id,
                "asset_name": asset_name,
                "old_status": old_label,
                "new_status": new_label,
                "issue_url": issue_url,
            },
        )
        logger.info(
            f"Issue status notification sent [report_id={report_id}, recipient={reporter_email}, {old_status!r} -> {new_status!r}]"
        )
