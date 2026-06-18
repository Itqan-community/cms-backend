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
