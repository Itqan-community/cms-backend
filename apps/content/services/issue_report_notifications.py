from __future__ import annotations

import logging

from django.conf import settings
from django.utils.functional import lazy
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from apps.content.models import ContentIssueReport, ContentIssueReportComment
from apps.content.services.issue_context import format_issue_context
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
            subject=format_lazy(
                _("Your issue status has been updated: {old_status} → {new_status}"),
                old_status=old_label,
                new_status=new_label,
            ),
            recipients=[reporter_email],
            template="emails/issue_status_update.html",
            context={
                "report_id": report_id,
                "asset_name": asset_name,
                # Lazy, so it renders in each recipient's language.
                "context_label": lazy(format_issue_context, str)(report.context) if report.context else "",
                "old_status": old_label,
                "new_status": new_label,
                "issue_url": issue_url,
            },
        )
        logger.info(
            f"Issue status notification sent [report_id={report_id}, recipient={reporter_email}, {old_status!r} -> {new_status!r}]"
        )

    def notify_comment_added(self, comment_id: int) -> None:
        """Email a new comment to the reporter; the publisher never sees their address."""
        try:
            comment = ContentIssueReportComment.objects.select_related(
                "report__reporter", "report__asset__publisher"
            ).get(pk=comment_id)
        except ContentIssueReportComment.DoesNotExist:
            logger.warning(f"ContentIssueReportComment not found, skipping email [comment_id={comment_id}]")
            return

        report = comment.report
        reporter_email = report.reporter.email
        if not reporter_email:
            logger.warning(f"Reporter has no email, skipping [report_id={report.pk}, comment_id={comment_id}]")
            return

        asset = report.asset
        asset_name = asset.name if asset else f"Issue #{report.pk}"
        portal_base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")

        email_service.send_email(
            subject=format_lazy(_("New reply on your issue report for {asset_name}"), asset_name=asset_name),
            recipients=[reporter_email],
            template="emails/issue_comment.html",
            context={
                "report_id": report.pk,
                "publisher_name": asset.publisher.name if asset else "",
                "asset_name": asset_name,
                "context_label": lazy(format_issue_context, str)(report.context) if report.context else "",
                "comment_body": comment.body,
                "asset_url": f"{portal_base}/gallery/asset/{asset.pk}" if asset else portal_base,
            },
        )
        logger.info(f"Issue comment notification sent [report_id={report.pk}, comment_id={comment_id}]")
