from __future__ import annotations

from django.contrib.auth.models import Group as PermissionsGroup
from django.db import transaction

from apps.core.permissions import PermissionChoice
from apps.publishers.models import PublisherMember
from apps.publishers.repositories.publisher_member import PublisherMemberRepository

# READ-only baseline granted to every active member (staff and admin).
PUBLISHER_MEMBER_GROUP = "Publisher Member"
PUBLISHER_MEMBER_GROUP_PERMS = [
    PermissionChoice.PORTAL_ACCESS.value,
    PermissionChoice.PORTAL_READ_RECITER.value,
    PermissionChoice.PORTAL_READ_RECITATION.value,
    PermissionChoice.PORTAL_READ_TAFSIR.value,
    PermissionChoice.PORTAL_READ_TRANSLATION.value,
    PermissionChoice.PORTAL_READ_PUBLISHER.value,
    PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS.value,
]

# Member-management permissions, granted to admin-role members on top of the baseline.
PUBLISHER_ADMIN_GROUP = "Publisher Member Admin"
PUBLISHER_ADMIN_GROUP_PERMS = [
    PermissionChoice.PORTAL_ACCESS.value,
    PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS.value,
    PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS.value,
    PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS.value,
    PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS.value,
]


class PublisherMemberService:
    def __init__(self, repo: PublisherMemberRepository | None = None) -> None:
        self.repo = repo or PublisherMemberRepository()

    def _base_group(self) -> PermissionsGroup:
        return PermissionsGroup.objects.get(name=PUBLISHER_MEMBER_GROUP)

    def _admin_group(self) -> PermissionsGroup:
        return PermissionsGroup.objects.get(name=PUBLISHER_ADMIN_GROUP)

    def grant_member_perms(self, member: PublisherMember) -> None:
        """Grant the READ baseline to any member; add the admin group for admins."""
        member.user.groups.add(self._base_group())
        if member.role == PublisherMember.RoleChoice.ADMIN:
            member.user.groups.add(self._admin_group())

    def revoke_member_perms(self, member: PublisherMember) -> None:
        """Remove both groups (member is being removed)."""
        member.user.groups.remove(self._base_group(), self._admin_group())

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
                # Base READ group stays; only the admin group toggles with the role.
                if new_role == PublisherMember.RoleChoice.ADMIN:
                    member.user.groups.add(self._admin_group())
                else:
                    member.user.groups.remove(self._admin_group())
        return member

    @transaction.atomic
    def delete_member(self, member: PublisherMember) -> None:
        if member.status == PublisherMember.StatusChoice.ACTIVE:
            self.revoke_member_perms(member)
        self.repo.delete_member(member)
