from __future__ import annotations

import logging

from django.conf import settings

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

    def send_publisher_new_request_email(self, request_id: int) -> None:
        req = self.repo.get_by_id(request_id)
        if req is None:
            logger.warning(f"AssetAccessRequest not found, skipping new-request email [request_id={request_id}]")
            return

        publisher = req.asset.publisher
        if not publisher.contact_email:
            logger.warning(f"Publisher has no contact_email, skipping new-request email [publisher_id={publisher.id}]")
            return
        recipients = [publisher.contact_email]

        portal_base = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
        email_service.send_email(
            subject=f"New access request for {req.asset.name}",
            recipients=recipients,
            template="emails/access_request_new.html",
            context={
                "asset_name": req.asset.name,
                "developer_name": req.developer_user.name,
                "auto_accepted": req.status == AssetAccessRequest.StatusChoice.APPROVED,
                "access_requests_url": f"{portal_base}/portal/access-requests",
            },
        )
        logger.info(f"Publisher new-request email sent [request_id={request_id}, recipients={len(recipients)}]")
