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

    def _groups_from_other_memberships(self, member: PublisherMember) -> set[int]:
        """Group ids this user still needs for their *other* publisher memberships.

        Django groups are global while membership is per-publisher, so a group must
        only be stripped once no remaining active membership depends on it.
        """
        return set(
            self.repo.other_active_membership_group_ids(
                user_id=member.user_id, exclude_member_id=member.id, publisher_id=member.publisher_id
            )
        )

    def grant_member_perms(self, member: PublisherMember) -> None:
        """Apply the member's group to the user."""
        member.user.groups.add(member.group)

    def revoke_member_perms(self, member: PublisherMember) -> None:
        """Remove this membership's group unless another membership still needs it."""
        if member.group_id not in self._groups_from_other_memberships(member):
            member.user.groups.remove(member.group)

    @transaction.atomic
    def update_member(self, member: PublisherMember, *, fields: dict) -> PublisherMember:
        name = fields.pop("name", None)
        if name is not None:
            member.user.name = name
            member.user.save(update_fields=["name"])
        new_group_id = fields.get("group_id")
        if new_group_id is not None and new_group_id != member.group_id:
            new_group = self.groups.resolve_assignable_group(new_group_id)
            previous_group = member.group
            self.repo.set_group(member, new_group)
            if member.status == PublisherMember.StatusChoice.ACTIVE:
                if previous_group.id not in self._groups_from_other_memberships(member):
                    member.user.groups.remove(previous_group)
                member.user.groups.add(new_group)
        return member

    @transaction.atomic
    def delete_member(self, member: PublisherMember) -> None:
        if member.status == PublisherMember.StatusChoice.ACTIVE:
            self.revoke_member_perms(member)
        self.repo.delete_member(member)
