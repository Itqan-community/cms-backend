from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def send_publisher_member_invitation_email(invitation_id: int, raw_token: str) -> None:
    logger.info(f"Task started [task=send_publisher_member_invitation_email, invitation_id={invitation_id}]")
    from apps.publishers.services.publisher_member_notification_service import PublisherMemberNotificationService

    PublisherMemberNotificationService().send_invitation_email(invitation_id, raw_token)
    logger.info(f"Task completed [task=send_publisher_member_invitation_email, invitation_id={invitation_id}]")


@shared_task
def send_publisher_member_activated_email(member_id: int, password: str | None = None) -> None:
    logger.info(f"Task started [task=send_publisher_member_activated_email, member_id={member_id}]")
    from apps.publishers.services.publisher_member_notification_service import PublisherMemberNotificationService

    PublisherMemberNotificationService().send_activation_email(member_id, password)
    logger.info(f"Task completed [task=send_publisher_member_activated_email, member_id={member_id}]")


@shared_task
def expire_publisher_member_invitations() -> int:
    """Mark all pending publisher member invitations past their expiry as EXPIRED."""
    logger.info("Task started [task=expire_publisher_member_invitations]")
    from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService

    expired_count = PublisherMemberInvitationService().expire_overdue_invitations()
    logger.info(f"Task completed [task=expire_publisher_member_invitations, expired={expired_count}]")
    return expired_count


@shared_task(bind=True, max_retries=3)
def send_publisher_inquiry_email(self, inquiry: dict[str, str]) -> None:
    """Deliver a landing-page "contact us to join" request to the Fanar team; retries with linear back-off."""
    logger.info("Task started [task=send_publisher_inquiry_email]")
    try:
        from apps.publishers.services.publisher_inquiry import PublisherInquiryService

        PublisherInquiryService().send_email(inquiry)
        logger.info("Task completed [task=send_publisher_inquiry_email]")
    except Exception as exc:
        logger.error(f"Task failed [task=send_publisher_inquiry_email]: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1)) from exc
