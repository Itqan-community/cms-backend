from __future__ import annotations

import logging

from django.conf import settings

from apps.core.services.email import email_service
from apps.publishers.repositories.publisher_member import PublisherMemberRepository
from apps.publishers.repositories.publisher_member_invitation import PublisherMemberInvitationRepository

logger = logging.getLogger(__name__)


class PublisherMemberNotificationService:
    def __init__(
        self,
        repo: PublisherMemberInvitationRepository | None = None,
        member_repo: PublisherMemberRepository | None = None,
    ) -> None:
        self.repo = repo or PublisherMemberInvitationRepository()
        self.member_repo = member_repo or PublisherMemberRepository()

    def send_invitation_email(self, invitation_id: int, raw_token: str) -> None:
        try:
            inv = self.repo.get_for_email(invitation_id)
        except Exception:
            logger.warning(f"Invitation not found, skipping email [invitation_id={invitation_id}]")
            return

        role_display = inv.member.get_role_display()
        accept_url = f"{settings.FRONTEND_BASE_URL}/portal/invitations/accept?token={raw_token}"
        email_service.send_email(
            subject=f"You're invited to {inv.publisher.name}",
            recipients=[inv.email],
            template="emails/publisher_member_invitation.html",
            context={
                "publisher_name": inv.publisher.name,
                "invited_by_name": inv.invited_by.name if inv.invited_by else "An administrator",
                "role": role_display,
                "accept_url": accept_url,
                "expires_at": inv.expires_at.date().isoformat(),
            },
        )
        logger.info(f"Invitation email sent [invitation_id={invitation_id}]")

    def send_activation_email(self, member_id: int, password: str | None) -> None:
        try:
            member = self.member_repo.get_with_relations(member_id)
        except Exception:
            logger.warning(f"Member not found, skipping activation email [member_id={member_id}]")
            return

        email_service.send_email(
            subject=f"Welcome to {member.publisher.name}",
            recipients=[member.user.email],
            template="emails/publisher_member_activated.html",
            context={
                "publisher_name": member.publisher.name,
                "password": password,
                "login_url": f"{settings.FRONTEND_BASE_URL}/account/login",
            },
        )
        logger.info(f"Activation email sent [member_id={member_id}]")
