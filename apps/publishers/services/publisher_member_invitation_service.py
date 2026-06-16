from __future__ import annotations

import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.repositories.publisher_member import PublisherMemberRepository
from apps.publishers.repositories.publisher_member_invitation import PublisherMemberInvitationRepository
from apps.publishers.services.publisher_member_service import PublisherMemberService
from apps.publishers.tasks import send_publisher_member_activated_email, send_publisher_member_invitation_email
from apps.users.models import User


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


class PublisherMemberInvitationService:
    def __init__(
        self,
        repo: PublisherMemberInvitationRepository | None = None,
        members: PublisherMemberService | None = None,
        member_repo: PublisherMemberRepository | None = None,
    ) -> None:
        self.repo = repo or PublisherMemberInvitationRepository()
        self.members = members or PublisherMemberService()
        self.member_repo = member_repo or PublisherMemberRepository()

    def _expiry(self):
        return timezone.now() + timezone.timedelta(days=settings.PUBLISHER_MEMBER_INVITATION_EXPIRY_DAYS)

    def expire_overdue_invitations(self) -> int:
        now = timezone.now()
        invitations = list(self.repo.get_expired_pending(now=now))
        return self.repo.mark_expired(invitations, now=now)

    @transaction.atomic
    def create_invitation(
        self, *, publisher: Publisher, email: str, role: str, invited_by: User
    ) -> tuple[PublisherMember, PublisherMemberInvitation, str]:
        email = email.lower().strip()

        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(email=email, password=None, is_active=False)
            user.set_unusable_password()
            user.save(update_fields=["password"])

        member = self.member_repo.select_for_update_member(user=user, publisher=publisher)
        if member is not None and member.status == PublisherMember.StatusChoice.ACTIVE:
            raise ItqanError(
                error_name="already_a_member",
                message=_("This user is already a member of this publisher."),
                status_code=409,
            )
        if member is None:
            member = self.member_repo.create_member(
                user=user, publisher=publisher, role=role, status=PublisherMember.StatusChoice.PENDING
            )

        now = timezone.now()
        self.repo.cancel_pending_invitations(member=member, cancelled_by=invited_by, now=now)
        invitation, raw_token = self._create_invitation_row(member, invited_by)
        return member, invitation, raw_token

    def _create_invitation_row(
        self, member: PublisherMember, invited_by: User
    ) -> tuple[PublisherMemberInvitation, str]:
        raw_token = secrets.token_urlsafe(32)
        invitation = self.repo.create_invitation(
            publisher=member.publisher,
            invited_by=invited_by,
            member=member,
            token_hash=_hash(raw_token),
            expires_at=self._expiry(),
        )
        transaction.on_commit(lambda: send_publisher_member_invitation_email.delay(invitation.id, raw_token))
        return invitation, raw_token

    @transaction.atomic
    def resend(self, invitation: PublisherMemberInvitation, actor: User):
        if invitation.status != PublisherMemberInvitation.StatusChoice.PENDING:
            raise ItqanError(
                error_name="invalid_invitation",
                message=_("Only pending invitations can be resent."),
                status_code=400,
            )
        member = invitation.member
        now = timezone.now()
        self.repo.cancel_pending_invitations(member=member, cancelled_by=actor, now=now)
        new_invitation, raw_token = self._create_invitation_row(member, actor)
        return member, new_invitation, raw_token

    @transaction.atomic
    def cancel(self, invitation: PublisherMemberInvitation, cancelled_by: User) -> None:
        if invitation.status != PublisherMemberInvitation.StatusChoice.PENDING:
            raise ItqanError(
                error_name="invalid_invitation",
                message=_("Only pending invitations can be cancelled."),
                status_code=400,
            )
        now = timezone.now()
        self.repo.mark_cancelled(invitation, cancelled_by=cancelled_by, now=now)
        invitation.member.delete()

    def get_invitation_details(self, raw_token: str) -> PublisherMemberInvitation:
        invitation = self.repo.get_by_token_hash(_hash(raw_token))
        if (
            invitation is None
            or invitation.status != PublisherMemberInvitation.StatusChoice.PENDING
            or invitation.expires_at < timezone.now()
        ):
            raise ItqanError(
                error_name="invalid_invitation",
                message=_("This invitation is no longer valid."),
                status_code=400,
            )
        return invitation

    @transaction.atomic
    def accept_invitation(self, raw_token: str) -> PublisherMemberInvitation:
        invitation = self.repo.lock_by_token_hash(_hash(raw_token))
        if invitation is None or invitation.status != PublisherMemberInvitation.StatusChoice.PENDING:
            raise ItqanError(
                error_name="invalid_invitation",
                message=_("This invitation is no longer valid."),
                status_code=400,
            )
        if invitation.expires_at < timezone.now():
            self.repo.mark_expired([invitation])
            raise ItqanError(
                error_name="invalid_invitation",
                message=_("This invitation is no longer valid."),
                status_code=400,
            )

        member = invitation.member
        user = member.user
        generated_password = None
        if not user.has_usable_password():
            generated_password = secrets.token_urlsafe(12)
            user.set_password(generated_password)
        user.is_active = True
        user.save(update_fields=["password", "is_active"])

        self.member_repo.set_status(member, PublisherMember.StatusChoice.ACTIVE)
        self.members.grant_member_perms(member)

        now = timezone.now()
        self.repo.mark_accepted(invitation, now=now)

        transaction.on_commit(lambda: send_publisher_member_activated_email.delay(member.id, generated_password))
        return invitation
