"""Helpers for tests that need publisher permission groups.

PublisherMember.group is a required FK, so every test that builds a membership
needs a real Group row. Publisher groups are defined by admins in the portal and
are not seeded, so these helpers create permission-less fixture groups.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission

from apps.core.permissions import PermissionChoice
from apps.users.services.group import ITQAN_INTERNAL_GROUP

PUBLISHER_MEMBER_GROUP = "Publisher Member"
PUBLISHER_ADMIN_GROUP = "Publisher Member Admin"


def _group(name: str, permissions: tuple[PermissionChoice, ...]) -> Group:
    group, _ = Group.objects.get_or_create(name=name)
    if permissions:
        group.permissions.add(*Permission.objects.filter(codename__in=[p.value for p in permissions]))
    return group


def member_group(*permissions: PermissionChoice) -> Group:
    """A fixture group standing in for a regular member's role, granted ``permissions``."""
    return _group(PUBLISHER_MEMBER_GROUP, permissions)


def admin_group(*permissions: PermissionChoice) -> Group:
    """A fixture group standing in for an admin member's role, granted ``permissions``."""
    return _group(PUBLISHER_ADMIN_GROUP, permissions)


def itqan_internal_group() -> Group:
    """The all-permissions internal group, which must never be assignable."""
    group, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
    return group
