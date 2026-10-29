"""Resolve which portal permissions a user holds at a given publisher.

A user's permissions at a publisher are their *global* permissions (direct user permissions
and global groups such as Itqan Internal) plus the permissions of the group (role) on their
ACTIVE membership at that publisher. Publisher roles never leak across publishers: a role is
only counted at the publisher whose membership carries it, even if the group is also present
in ``user.groups``.

Without a publisher (no ``X-Tenant``) only global permissions apply, plus ``portal_access``
for users with any active membership so the portal can load its tenant picker. Leaving the
header out must never yield the union of the user's roles across publishers.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from plain_permissions.models import Permission as CustomPermission

from apps.core.permissions import PermissionChoice
from apps.publishers.models import Publisher, PublisherMember

if TYPE_CHECKING:
    from apps.users.models import User

__all__ = ["effective_permissions", "effective_permissions_by_publisher", "permissions_across_memberships"]

_CACHE_ATTR = "_effective_perm_cache"
_GLOBAL = "global"


def effective_permissions(user: User, publisher: Publisher | int | None) -> frozenset[str]:
    """Codenames ``user`` holds at ``publisher`` (or globally when ``publisher`` is None)."""
    if not _is_active_user(user):
        return frozenset()
    if user.is_superuser:
        return frozenset(PermissionChoice.values)  # type: ignore[attr-defined]

    publisher_id = publisher.id if isinstance(publisher, Publisher) else publisher
    cache = _cache(user)
    if publisher_id not in cache:
        if publisher_id is None:
            cache[None] = _global_permissions(user) | _tenantless_extras(user)
        else:
            effective_permissions_by_publisher(user, [publisher_id])
    return cache[publisher_id]


def effective_permissions_by_publisher(user: User, publisher_ids: Iterable[int]) -> dict[int, frozenset[str]]:
    """Like :func:`effective_permissions` for many publishers, in a fixed number of queries."""
    publisher_ids = list(publisher_ids)
    if not _is_active_user(user):
        return {publisher_id: frozenset() for publisher_id in publisher_ids}
    if user.is_superuser:
        everything = frozenset(PermissionChoice.values)  # type: ignore[attr-defined]
        return dict.fromkeys(publisher_ids, everything)

    cache = _cache(user)
    missing = [publisher_id for publisher_id in publisher_ids if publisher_id not in cache]
    if missing:
        global_perms = _global_permissions(user)
        by_publisher: dict[int, set[str]] = {publisher_id: set() for publisher_id in missing}
        rows = Permission.objects.filter(
            content_type=_content_type(),
            group__publisher_memberships__user=user,
            group__publisher_memberships__status=PublisherMember.StatusChoice.ACTIVE,
            group__publisher_memberships__publisher_id__in=missing,
        ).values_list("group__publisher_memberships__publisher_id", "codename")
        for publisher_id, codename in rows:
            by_publisher[publisher_id].add(codename)
        for publisher_id, codenames in by_publisher.items():
            cache[publisher_id] = global_perms | frozenset(codenames)
    return {publisher_id: cache[publisher_id] for publisher_id in publisher_ids}


def permissions_across_memberships(user: User) -> frozenset[str]:
    """Global permissions plus every ACTIVE membership's role, merged.

    Only for display compatibility (the profile's ``permissions``): it is the union the portal
    showed before roles were scoped per publisher. Never use it to authorize a request.
    """
    if not _is_active_user(user):
        return frozenset()
    publisher_ids = PublisherMember.objects.filter(user=user, status=PublisherMember.StatusChoice.ACTIVE).values_list(
        "publisher_id", flat=True
    )
    merged = set(effective_permissions(user, None))
    for codenames in effective_permissions_by_publisher(user, publisher_ids).values():
        merged |= codenames
    return frozenset(merged)


def _global_permissions(user: User) -> frozenset[str]:
    cache = _cache(user)
    if _GLOBAL not in cache:
        cache[_GLOBAL] = frozenset(
            Permission.objects.filter(content_type=_content_type())
            .filter(Q(user=user) | Q(group__in=user.groups.filter(publisher_group__isnull=True)))
            .values_list("codename", flat=True)
            .distinct()
        )
    return cache[_GLOBAL]


def _tenantless_extras(user: User) -> frozenset[str]:
    has_membership = PublisherMember.objects.filter(user=user, status=PublisherMember.StatusChoice.ACTIVE).exists()
    return frozenset({PermissionChoice.PORTAL_ACCESS.value}) if has_membership else frozenset()


def _is_active_user(user: User | None) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


def _cache(user: User) -> dict:
    # Per-instance, so it lives for one request (request.user is rebuilt each time).
    cache = user.__dict__.get(_CACHE_ATTR)
    if cache is None:
        cache = user.__dict__[_CACHE_ATTR] = {}
    return cache


def _content_type() -> ContentType:
    return ContentType.objects.get_for_model(CustomPermission)
