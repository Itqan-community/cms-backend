from __future__ import annotations

from itertools import groupby
import logging

from django.conf import settings
from django.utils.translation import gettext as _

from apps.content.models import AssetAccessRequest
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.core.services.email import email_service

logger = logging.getLogger(__name__)


class AccessRequestNotificationService:
    def __init__(self, repo: AssetAccessRequestRepository | None = None) -> None:
        self.repo = repo or AssetAccessRequestRepository()

    def send_developer_outcome_email(self, request_id: int) -> None:
        req = self.repo.get_by_id(request_id)
        if req is None:
            logger.warning(f"AssetAccessRequest not found, skipping outcome email [request_id={request_id}]")
            return

        recipient = req.developer_user.email
        if not recipient:
            logger.warning(f"Developer has no email, skipping [request_id={request_id}]")
            return

        if req.status == AssetAccessRequest.StatusChoice.APPROVED:
            email_service.send_email(
                subject=f"Your access request for {req.asset.name} was accepted",
                recipients=[recipient],
                template="emails/access_request_accepted.html",
                context={"asset_name": req.asset.name},
            )
        elif req.status == AssetAccessRequest.StatusChoice.REJECTED:
            email_service.send_email(
                subject=f"Your access request for {req.asset.name} was rejected",
                recipients=[recipient],
                template="emails/access_request_rejected.html",
                context={"asset_name": req.asset.name, "rejection_reason": req.rejection_reason},
            )
        else:
            return

        logger.info(f"Access request outcome email sent [request_id={request_id}, status={req.status}]")

    def notify_publishers_of_pending_requests(self) -> None:
        reqs = list(self.repo.list_pending_for_publisher_notification())

        if not reqs:
            return

        portal_base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
        access_requests_url = f"{portal_base}/admin/access-requests"

        for publisher, group in groupby(reqs, key=lambda r: r.asset.publisher):
            publisher_reqs = list(group)
            if not publisher.contact_email:
                logger.warning(
                    f"Publisher has no contact_email, skipping pending-access-request notification "
                    f"[publisher_id={publisher.id}, request_count={len(publisher_reqs)}]"
                )
                continue

            context = {
                "count": len(publisher_reqs),
                "requests": [
                    {
                        "asset_name": r.asset.name,
                        "developer_name": r.developer_user.name,
                        "intended_use": r.get_intended_use_display(),
                        "developer_access_reason": r.developer_access_reason,
                        "created_at": r.created_at,
                    }
                    for r in publisher_reqs
                ],
                "access_requests_url": access_requests_url,
            }
            try:
                email_service.send_email(
                    subject=_("You have {count} pending access request(s)").format(count=len(publisher_reqs)),
                    recipients=[publisher.contact_email],
                    template="emails/pending_access_requests_notification.html",
                    context=context,
                )
                logger.info(
                    f"Pending-access-request notification sent "
                    f"[publisher_id={publisher.id}, count={len(publisher_reqs)}, "
                    f"request_ids={[r.id for r in publisher_reqs]}]"
                )
            except Exception as exc:
                logger.exception(
                    f"Failed to send pending-access-request notification "
                    f"[publisher_id={publisher.id}, count={len(publisher_reqs)}]: {exc}"
                )
