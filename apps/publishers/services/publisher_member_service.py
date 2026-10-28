from __future__ import annotations

from django.db import transaction

from apps.publishers.models import PublisherMember
from apps.publishers.repositories.publisher_member import PublisherMemberRepository
from apps.users.services.group import ITQAN_INTERNAL_GROUP, GroupService

__all__ = [
    "ITQAN_INTERNAL_GROUP",
    "PublisherMemberService",
]


class PublisherMemberService:
    def __init__(
        self,
        repo: PublisherMemberRepository | None = None,
        groups: GroupService | None = None,
    ) -> None:
        self.repo = repo or PublisherMemberRepository()
        self.groups = groups or GroupService()

    @transaction.atomic
    def update_member(self, member: PublisherMember, *, fields: dict) -> PublisherMember:
        name = fields.pop("name", None)
        if name is not None:
            member.user.name = name
            member.user.save(update_fields=["name"])
        new_group_id = fields.get("group_id")
        if new_group_id is not None and new_group_id != member.group_id:
            # The membership carries the role; permissions are resolved from it per publisher,
            # so user.groups is left alone.
            self.repo.set_group(member, self.groups.resolve_assignable_group(new_group_id, member.publisher_id))
        return member

    @transaction.atomic
    def delete_member(self, member: PublisherMember) -> None:
        self.repo.delete_member(member)
