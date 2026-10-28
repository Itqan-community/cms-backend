"""Helpers for tests that need publisher permission groups.

PublisherMember.group is a required FK, so every test that builds a membership
needs a real Group row. Publisher groups are defined by admins in the portal and
are not seeded, so these helpers create fixture groups. Pass ``publisher`` to get a
publisher-owned role (the only kind the portal lists or assigns); without it the
group is global, which is enough wherever a test only needs the FK.
"""

from __future__ import annotations

import uuid

from django.contrib.auth.models import Group, Permission

from apps.core.permissions import PermissionChoice
from apps.publishers.models import Publisher, PublisherGroup
from apps.users.services.group import ITQAN_INTERNAL_GROUP

PUBLISHER_MEMBER_GROUP = "Publisher Member"
PUBLISHER_ADMIN_GROUP = "Publisher Member Admin"


def _grant(group: Group, permissions: tuple[PermissionChoice, ...]) -> Group:
    if permissions:
        group.permissions.add(*Permission.objects.filter(codename__in=[p.value for p in permissions]))
    return group


def publisher_role(
    publisher: Publisher, name: str, *permissions: PermissionChoice, name_ar: str | None = None
) -> Group:
    """A role owned by ``publisher``, named ``name`` (English; Arabic defaults to the same),
    granted ``permissions`` (get-or-create by English name)."""
    existing = PublisherGroup.objects.filter(publisher=publisher, name_en=name).select_related("group").first()
    if existing is not None:
        return _grant(existing.group, permissions)
    group = Group.objects.create(name=f"publisher:{publisher.id}:{uuid.uuid4().hex}")
    PublisherGroup.objects.create(group=group, publisher=publisher, name_en=name, name_ar=name_ar or name)
    return _grant(group, permissions)


def _group(name: str, permissions: tuple[PermissionChoice, ...], publisher: Publisher | None) -> Group:
    if publisher is not None:
        return publisher_role(publisher, name, *permissions)
    group, _ = Group.objects.get_or_create(name=name)
    return _grant(group, permissions)


def member_group(*permissions: PermissionChoice, publisher: Publisher | None = None) -> Group:
    """A fixture group standing in for a regular member's role, granted ``permissions``."""
    return _group(PUBLISHER_MEMBER_GROUP, permissions, publisher)


def admin_group(*permissions: PermissionChoice, publisher: Publisher | None = None) -> Group:
    """A fixture group standing in for an admin member's role, granted ``permissions``."""
    return _group(PUBLISHER_ADMIN_GROUP, permissions, publisher)


def itqan_internal_group() -> Group:
    """The all-permissions internal group, which must never be assignable."""
    group, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
    return group
