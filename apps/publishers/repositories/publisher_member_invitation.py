from __future__ import annotations

from django.utils import timezone

from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.users.models import User


class PublisherMemberInvitationRepository:
    def __init__(self) -> None:
        self.model = PublisherMemberInvitation

    def create_invitation(
        self,
        *,
        publisher: Publisher,
        invited_by: User,
        member: PublisherMember,
        token_hash: str,
        expires_at,
    ) -> PublisherMemberInvitation:
        return self.model.objects.create(
            publisher=publisher,
            invited_by=invited_by,
            member=member,
            token_hash=token_hash,
            expires_at=expires_at,
        )

    def cancel_pending_invitations(self, *, member: PublisherMember, cancelled_by: User, now) -> None:
        self.model.objects.filter(member=member, status=PublisherMemberInvitation.StatusChoice.PENDING).update(
            status=PublisherMemberInvitation.StatusChoice.CANCELLED,
            cancelled_at=now,
            cancelled_by=cancelled_by,
            updated_at=now,
        )

    def get_expired_pending(self, *, now):
        return self.model.objects.filter(status=PublisherMemberInvitation.StatusChoice.PENDING, expires_at__lt=now)

    def get_pending_for_member(self, member: PublisherMember) -> PublisherMemberInvitation | None:
        return self.model.objects.filter(member=member, status=PublisherMemberInvitation.StatusChoice.PENDING).first()

    def lock_by_token_hash(self, token_hash: str) -> PublisherMemberInvitation | None:
        return (
            self.model.objects.select_for_update(of=("self",))
            .select_related("member", "member__user", "publisher")
            .filter(token_hash=token_hash)
            .first()
        )

    def mark_cancelled(self, invitation: PublisherMemberInvitation, *, cancelled_by: User, now) -> None:
        invitation.status = PublisherMemberInvitation.StatusChoice.CANCELLED
        invitation.cancelled_at = now
        invitation.cancelled_by = cancelled_by
        invitation.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])

    def mark_expired(self, invitations: list[PublisherMemberInvitation], *, now=None) -> int:
        now = now or timezone.now()
        for invitation in invitations:
            invitation.status = PublisherMemberInvitation.StatusChoice.EXPIRED
            invitation.updated_at = now
        if invitations:
            self.model.objects.bulk_update(invitations, ["status", "updated_at"])
        return len(invitations)

    def mark_accepted(self, invitation: PublisherMemberInvitation, *, now) -> None:
        invitation.status = PublisherMemberInvitation.StatusChoice.ACCEPTED
        invitation.accepted_at = now
        invitation.token_hash = ""
        invitation.save(update_fields=["status", "accepted_at", "token_hash", "updated_at"])

    def get_for_email(self, invitation_id: int) -> PublisherMemberInvitation:
        return self.model.objects.select_related("publisher", "invited_by", "member", "member__user").get(
            pk=invitation_id
        )
