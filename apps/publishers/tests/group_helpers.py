"""Helpers for tests that need the seeded publisher permission groups.

PublisherMember.group is a required FK, so every test that builds a membership
needs a real Group row. The groups are normally created by the publishers app's
post_migrate seeder; these helpers are get_or_create so tests stay independent
of seeding order.
"""

from __future__ import annotations

from django.contrib.auth.models import Group

from apps.publishers.services.publisher_member_service import PUBLISHER_ADMIN_GROUP, PUBLISHER_MEMBER_GROUP
from apps.users.services.group import ITQAN_INTERNAL_GROUP


def member_group() -> Group:
    """The READ-baseline group previously implied by role="staff"."""
    group, _ = Group.objects.get_or_create(name=PUBLISHER_MEMBER_GROUP)
    return group


def admin_group() -> Group:
    """The member-management group previously implied by role="admin"."""
    group, _ = Group.objects.get_or_create(name=PUBLISHER_ADMIN_GROUP)
    return group


def itqan_internal_group() -> Group:
    """The all-permissions internal group, which must never be assignable."""
    group, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
    return group
