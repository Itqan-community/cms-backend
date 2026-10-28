from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import ProtectedError
from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.services.permissions import PermissionHierarchyService
from apps.publishers.services.effective_permissions import effective_permissions
from apps.users.repositories.group import ITQAN_INTERNAL_GROUP, GroupRepository

if TYPE_CHECKING:
    from django.contrib.auth.models import Group
    from django.db.models import QuerySet

    from apps.users.models import User

__all__ = ["ITQAN_INTERNAL_GROUP", "GroupService"]

_NAME_MAX_LENGTH = 150  # matches django.contrib.auth.models.Group.name


class GroupService:
    def __init__(
        self,
        repo: GroupRepository | None = None,
        hierarchy: PermissionHierarchyService | None = None,
    ) -> None:
        self.repo = repo or GroupRepository()
        self.hierarchy = hierarchy or PermissionHierarchyService()

    def assignable_groups_qs(self, publisher_id: int) -> QuerySet[Group]:
        """The roles ``publisher_id`` owns, which are all that the portal lists or assigns.

        Global groups (Itqan Internal and other staff-only groups) and other publishers' roles
        are never offered.
        """
        return self.repo.assignable_qs(publisher_id)

    def resolve_assignable_group(self, group_id: int, publisher_id: int) -> Group:
        """Look up one of ``publisher_id``'s roles by id, rejecting any other id.

        Missing ids, global groups and other publishers' roles all raise the same error so the
        endpoint never confirms what exists outside the caller's publisher.
        """
        group = self.repo.get_assignable_by_id(group_id, publisher_id)
        if group is None:
            raise ItqanError(
                error_name="invalid_group",
                message=_("Group with id {id} is not available for assignment.").format(id=group_id),
                status_code=400,
            )
        return group

    def create(self, publisher_id: int, name: str) -> Group:
        name = self.validate_name(name, publisher_id=publisher_id)
        return self.repo.create_for_publisher(publisher_id, name)

    def rename(self, group_id: int, publisher_id: int, name: str) -> Group:
        group = self._get_or_404(group_id, publisher_id)
        name = self.validate_name(name, exclude_id=group_id, publisher_id=publisher_id)
        return self.repo.rename(group, name)

    def set_permissions(self, group_id: int, publisher_id: int, permissions: list[str], *, editor: User) -> Group:
        """Replace the group's permissions with the implied closure of ``permissions``.

        Each submitted codename is validated against :class:`PermissionChoice`; unknown
        codenames are rejected. The hierarchy is applied (e.g. CREATE pulls in READ) before
        the group's permission set is overwritten. Unless ``editor`` is Itqan staff, every
        permission in that closure must be one the editor holds at this publisher, so a role
        can never be used to escalate beyond its editor's own rights.
        """
        group = self._get_or_404(group_id, publisher_id)
        choices = self._validate_permissions(permissions)
        self._check_grantable(editor, publisher_id, choices)
        rows = self.hierarchy.implied_rows(choices)
        return self.repo.set_permissions(group, rows)

    def delete(self, group_id: int, publisher_id: int) -> None:
        group = self._get_or_404(group_id, publisher_id)
        try:
            self.repo.delete(group)
        except ProtectedError as exc:
            raise ItqanError(
                error_name="group_in_use",
                message=_("This group is assigned to members and cannot be deleted."),
                status_code=400,
            ) from exc

    def validate_name(self, name: str, *, exclude_id: int | None = None, publisher_id: int | None = None) -> str:
        """Return the normalised ``name``, or raise :class:`ItqanError` if it is not usable.

        Names are unique among ``publisher_id``'s roles, or among all groups when it is None
        (the Django admin, which saves global groups through a ``ModelForm``).
        """
        name = self._validate_name(name)
        if self.repo.name_exists(name, exclude_id=exclude_id, publisher_id=publisher_id):
            raise ItqanError(
                error_name="group_already_exists",
                message=_("A group with this name already exists."),
                status_code=400,
            )
        return name

    def apply_permissions(self, group: Group, permissions: list[str] | list[PermissionChoice]) -> Group:
        """Replace ``group``'s permissions with the implied closure of ``permissions``.

        Like :meth:`set_permissions` but for callers that already hold the ``Group`` instance
        and so do not need the id lookup.
        """
        choices = self._validate_permissions([str(permission) for permission in permissions])
        rows = self.hierarchy.implied_rows(choices)
        return self.repo.set_permissions(group, rows)

    def delete_group(self, group: Group) -> None:
        """Delete an already-loaded ``group``, bypassing the id lookup of :meth:`delete`."""
        self.repo.delete(group)

    def _check_grantable(self, editor: User, publisher_id: int, choices: list[PermissionChoice]) -> None:
        if editor.is_staff or editor.is_superuser:
            return
        requested = {permission.value for permission in self.hierarchy.with_implied(choices)}
        not_held = requested - effective_permissions(editor, publisher_id)
        if not_held:
            raise ItqanError(
                error_name="permission_not_grantable",
                message=_("You cannot grant permissions you do not hold: {permissions}.").format(
                    permissions=", ".join(sorted(not_held))
                ),
                status_code=400,
            )

    def _get_or_404(self, group_id: int, publisher_id: int) -> Group:
        group = self.repo.get_assignable_by_id(group_id, publisher_id)
        if group is None:
            raise ItqanError(
                error_name="group_not_found",
                message=_("Group with id {id} not found.").format(id=group_id),
                status_code=404,
            )
        return group

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if not name:
            raise ItqanError(
                error_name="group_name_required",
                message=_("Group name must not be empty."),
                status_code=400,
            )
        if len(name) > _NAME_MAX_LENGTH:
            raise ItqanError(
                error_name="group_name_too_long",
                message=_("Group name must not exceed %(max)d characters.") % {"max": _NAME_MAX_LENGTH},
                status_code=400,
            )
        return name

    @staticmethod
    def _validate_permissions(permissions: list[str]) -> list[PermissionChoice]:
        valid = {choice.value for choice in PermissionChoice}
        unknown = [permission for permission in permissions if permission not in valid]
        if unknown:
            raise ItqanError(
                error_name="invalid_permission",
                message=_("Unknown permissions: {permissions}.").format(permissions=", ".join(sorted(unknown))),
                status_code=400,
            )
        return [PermissionChoice(permission) for permission in permissions]
