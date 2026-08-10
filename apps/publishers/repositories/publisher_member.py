from __future__ import annotations

from django.contrib.auth.models import Group

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

    def create_member(self, *, user: User, publisher: Publisher, group: Group, status: str) -> PublisherMember:
        return self.model.objects.create(user=user, publisher=publisher, group=group, status=status)

    def set_status(self, member: PublisherMember, status: str) -> PublisherMember:
        member.status = status
        member.save(update_fields=["status", "updated_at"])
        return member

    def set_group(self, member: PublisherMember, group: Group) -> PublisherMember:
        member.group = group
        member.save(update_fields=["group", "updated_at"])
        return member

    def other_active_membership_group_ids(
        self, *, user_id: int, exclude_member_id: int | None, publisher_id: int
    ) -> list[int]:
        """Group ids from this user's other ACTIVE memberships, excluding the given one."""
        qs = self.model.objects.filter(user_id=user_id, status=PublisherMember.StatusChoice.ACTIVE)
        if exclude_member_id is not None:
            qs = qs.exclude(id=exclude_member_id)
        else:
            qs = qs.exclude(publisher_id=publisher_id)
        return list(qs.values_list("group_id", flat=True))

    def delete_member(self, member: PublisherMember) -> None:
        member.delete()

    def get_with_relations(self, member_id: int) -> PublisherMember:
        return self.model.objects.select_related("user", "publisher", "group").get(pk=member_id)
