from __future__ import annotations

from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class PublisherMemberRepository:
    def __init__(self) -> None:
        self.model = PublisherMember

    def get_active_member(self, *, user: User, publisher: Publisher) -> PublisherMember | None:
        return self.model.objects.filter(
            user=user, publisher=publisher, status=PublisherMember.StatusChoice.ACTIVE
        ).first()

    def select_for_update_member(self, *, user: User, publisher: Publisher) -> PublisherMember | None:
        return self.model.objects.select_for_update().filter(user=user, publisher=publisher).first()

    def create_member(self, *, user: User, publisher: Publisher, role: str, status: str) -> PublisherMember:
        return self.model.objects.create(user=user, publisher=publisher, role=role, status=status)

    def set_status(self, member: PublisherMember, status: str) -> PublisherMember:
        member.status = status
        member.save(update_fields=["status", "updated_at"])
        return member

    def set_role(self, member: PublisherMember, role: str) -> PublisherMember:
        member.role = role
        member.save(update_fields=["role", "updated_at"])
        return member

    def delete_member(self, member: PublisherMember) -> None:
        member.delete()

    def get_with_relations(self, member_id: int) -> PublisherMember:
        return self.model.objects.select_related("user", "publisher").get(pk=member_id)
