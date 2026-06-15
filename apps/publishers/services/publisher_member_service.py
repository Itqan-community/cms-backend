from __future__ import annotations

from django.contrib.auth.models import Group as PermissionsGroup
from django.db import transaction

from apps.publishers.models import PublisherMember
from apps.publishers.repositories.publisher_member import PublisherMemberRepository

PUBLISHER_ADMIN_GROUP = "Publisher Member Admin"


class PublisherMemberService:
    def __init__(self, repo: PublisherMemberRepository | None = None) -> None:
        self.repo = repo or PublisherMemberRepository()

    def grant_member_perms(self, member: PublisherMember) -> None:
        group = PermissionsGroup.objects.get(name=PUBLISHER_ADMIN_GROUP)
        member.user.groups.add(group)

    def revoke_member_perms(self, member: PublisherMember) -> None:
        group = PermissionsGroup.objects.get(name=PUBLISHER_ADMIN_GROUP)
        member.user.groups.remove(group)

    @transaction.atomic
    def update_member(self, member: PublisherMember, *, fields: dict) -> PublisherMember:
        name = fields.pop("name", None)
        if name is not None:
            member.user.name = name
            member.user.save(update_fields=["name"])
        new_role = fields.get("role")
        if new_role is not None and new_role != member.role:
            self.repo.set_role(member, new_role)
            if member.status == PublisherMember.StatusChoice.ACTIVE:
                if new_role == PublisherMember.RoleChoice.ADMIN:
                    self.grant_member_perms(member)
                else:
                    self.revoke_member_perms(member)
        return member

    @transaction.atomic
    def delete_member(self, member: PublisherMember) -> None:
        if member.status == PublisherMember.StatusChoice.ACTIVE:
            self.revoke_member_perms(member)
        self.repo.delete_member(member)
