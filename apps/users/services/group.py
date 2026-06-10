from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.services.permissions import PermissionHierarchyService
from apps.users.repositories.group import GroupRepository

if TYPE_CHECKING:
    from django.contrib.auth.models import Group

_NAME_MAX_LENGTH = 150  # matches django.contrib.auth.models.Group.name


class GroupService:
    def __init__(
        self,
        repo: GroupRepository | None = None,
        hierarchy: PermissionHierarchyService | None = None,
    ) -> None:
        self.repo = repo or GroupRepository()
        self.hierarchy = hierarchy or PermissionHierarchyService()

    def create(self, name: str) -> Group:
        name = self._validate_name(name)
        if self.repo.name_exists(name):
            raise ItqanError(
                error_name="group_already_exists",
                message=_("A group with this name already exists."),
                status_code=400,
            )
        return self.repo.create(name)

    def rename(self, group_id: int, name: str) -> Group:
        group = self._get_or_404(group_id)
        name = self._validate_name(name)
        if self.repo.name_exists(name, exclude_id=group_id):
            raise ItqanError(
                error_name="group_already_exists",
                message=_("A group with this name already exists."),
                status_code=400,
            )
        return self.repo.rename(group, name)

    def set_permissions(self, group_id: int, permissions: list[str]) -> Group:
        """Replace the group's permissions with the implied closure of ``permissions``.

        Each submitted codename is validated against :class:`PermissionChoice`; unknown
        codenames are rejected. The hierarchy is applied (e.g. CREATE pulls in READ) before
        the group's permission set is overwritten.
        """
        group = self._get_or_404(group_id)
        choices = self._validate_permissions(permissions)
        rows = self.hierarchy.implied_rows(choices)
        return self.repo.set_permissions(group, rows)

    def delete(self, group_id: int) -> None:
        group = self._get_or_404(group_id)
        self.repo.delete(group)

    def _get_or_404(self, group_id: int) -> Group:
        group = self.repo.get_by_id(group_id)
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
