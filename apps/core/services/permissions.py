"""Service layer for assigning permissions according to the permission hierarchy.

A "stronger" permission logically implies the weaker ones within its resource group
(DELETE -> UPDATE -> CREATE -> READ). When a permission is granted to a user or a group,
this service expands it to its full implied set and assigns all of them together, so a
caller never ends up with CREATE but no READ.

Revocation walks the hierarchy in the opposite direction: removing a permission also
removes every permission that depends on it. Revoking READ therefore strips CREATE,
UPDATE and DELETE too, since those make no sense without READ.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from plain_permissions.models import Permission as CustomPermission

from apps.core.permissions import PERMISSION_IMPLICATIONS, PermissionChoice

if TYPE_CHECKING:
    from django.contrib.auth.models import Group

    from apps.users.models import User


class PermissionHierarchyService:
    """Expand and assign permissions following the permission waterfall."""

    def __init__(self, implications: dict[PermissionChoice, frozenset[PermissionChoice]] | None = None) -> None:
        self._implications = implications or PERMISSION_IMPLICATIONS
        self._dependents = self._build_dependents(self._implications)

    @staticmethod
    def _build_dependents(
        implications: dict[PermissionChoice, frozenset[PermissionChoice]],
    ) -> dict[PermissionChoice, set[PermissionChoice]]:
        """Invert the implication graph: map each permission to the ones that depend on it.

        If ``CREATE`` implies ``READ``, then ``READ`` has ``CREATE`` as a dependent, so
        revoking ``READ`` must also revoke ``CREATE``.
        """
        dependents: dict[PermissionChoice, set[PermissionChoice]] = {}
        for permission, implied in implications.items():
            for weaker in implied:
                dependents.setdefault(weaker, set()).add(permission)
        return dependents

    def with_implied(self, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Return ``permissions`` plus every weaker permission they imply.

        Walks the hierarchy towards weaker permissions, e.g. ``with_implied([PORTAL_DELETE_RECITER])``
        yields ``{DELETE, UPDATE, CREATE, READ}`` for reciters. Use this when granting, so a
        caller never ends up with CREATE but no READ.
        """
        return self._closure(permissions, self._implications)

    def with_dependents(self, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Return ``permissions`` plus every stronger permission that depends on them.

        Walks the hierarchy towards stronger permissions — the inverse of :meth:`with_implied`.
        ``with_dependents([PORTAL_READ_RECITER])`` yields ``{READ, CREATE, UPDATE, DELETE}``,
        because none of the stronger permissions may survive once READ is gone. Use this when
        revoking.
        """
        return self._closure(permissions, self._dependents)

    def _closure(
        self,
        permissions: Iterable[PermissionChoice | str],
        edges: dict[PermissionChoice, frozenset[PermissionChoice] | set[PermissionChoice]],
    ) -> set[PermissionChoice]:
        """Transitive closure of ``permissions`` over the ``edges`` adjacency map.

        Iterative depth-first walk; cheap and avoids recursion limits even if the hierarchy
        grows deeper.
        """
        result: set[PermissionChoice] = set()
        stack = [self._coerce(permission) for permission in permissions]
        while stack:
            permission = stack.pop()
            if permission in result:
                continue
            result.add(permission)
            stack.extend(edges.get(permission, frozenset()))
        return result

    def grant_to_user(self, user: User, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Grant ``permissions`` (and everything they imply) to ``user``.

        Idempotent: re-granting already-held permissions is a no-op. Returns the full set
        of permission choices that were applied (the implied closure).
        """
        granted = self.with_implied(permissions)
        user.user_permissions.add(*self._to_permission_rows(granted))
        return granted

    def grant_to_group(self, group: Group, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Grant ``permissions`` (and everything they imply) to ``group``."""
        granted = self.with_implied(permissions)
        group.permissions.add(*self._to_permission_rows(granted))
        return granted

    def revoke_from_user(self, user: User, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Revoke ``permissions`` (and everything that depends on them) from ``user``.

        Idempotent: revoking permissions the user does not hold is a no-op. Returns the
        full set of permission choices that were removed (the dependents closure).
        """
        revoked = self.with_dependents(permissions)
        user.user_permissions.remove(*self._to_permission_rows(revoked))
        return revoked

    def revoke_from_group(self, group: Group, permissions: Iterable[PermissionChoice | str]) -> set[PermissionChoice]:
        """Revoke ``permissions`` (and everything that depends on them) from ``group``."""
        revoked = self.with_dependents(permissions)
        group.permissions.remove(*self._to_permission_rows(revoked))
        return revoked

    def implied_rows(self, permissions: Iterable[PermissionChoice | str]) -> list[Permission]:
        """Return the Django ``Permission`` rows for ``permissions`` plus everything they imply.

        Convenience for callers (e.g. setting a group's whole permission set) that need the
        implied closure as concrete ``Permission`` rows rather than just choices.
        """
        return self._to_permission_rows(self.with_implied(permissions))

    @staticmethod
    def _coerce(permission: PermissionChoice | str) -> PermissionChoice:
        if isinstance(permission, PermissionChoice):
            return permission
        return PermissionChoice(permission)

    @staticmethod
    def _to_permission_rows(permissions: Iterable[PermissionChoice]) -> list[Permission]:
        """Resolve permission choices to the Django ``Permission`` rows synced by plain_permissions."""
        content_type = ContentType.objects.get_for_model(CustomPermission)
        codenames = [str(permission.value) for permission in permissions]
        rows = list(Permission.objects.filter(content_type=content_type, codename__in=codenames))

        missing = set(codenames) - {row.codename for row in rows}
        if missing:
            raise ValueError(f"Permissions are not synced to the database: {sorted(missing)}. Run `manage.py migrate`.")
        return rows
