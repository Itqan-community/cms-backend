"""Resolve a request's publisher identity from the authenticated user."""

from __future__ import annotations

from django.core.cache import cache

_CACHE_ATTR = "_usage_tracking_resolved_publisher"
_REDIS_CACHE_TTL = 300  # 5 minutes


def resolve_publisher_from_request(request) -> tuple[int | None, str | None, str | None]:
    """Return ``(publisher_id, publisher_slug, publisher_name)`` for the request."""
    cached = getattr(request, _CACHE_ATTR, None)
    if cached is not None:
        return cached

    result = _resolve(request)
    try:
        setattr(request, _CACHE_ATTR, result)
    except (AttributeError, TypeError):
        pass
    return result


def _resolve(request) -> tuple[int | None, str | None, str | None]:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None, None, None

    user_pk = getattr(user, "pk", None)
    if user_pk is not None:
        redis_key = f"pub_resolver:user:{user_pk}"
        cached = cache.get(redis_key)
        if cached is not None:
            return cached

    result = _lookup_publisher_for_user(user)

    if user_pk is not None:
        cache.set(redis_key, result, _REDIS_CACHE_TTL)

    return result


def _lookup_publisher_for_user(owner) -> tuple[int | None, str | None, str | None]:
    """Database lookup, isolated for easy mocking in unit tests."""
    from apps.publishers.models import PublisherMember

    membership = (
        PublisherMember.objects.filter(user=owner, role=PublisherMember.RoleChoice.OWNER)
        .select_related("publisher")
        .first()
    )
    if membership is None:
        membership = PublisherMember.objects.filter(user=owner).select_related("publisher").first()
    if membership is None:
        return None, None, None
    return membership.publisher_id, membership.publisher.slug, membership.publisher.name
