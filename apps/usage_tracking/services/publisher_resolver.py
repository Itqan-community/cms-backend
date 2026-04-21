"""Resolve a request's publisher identity from its OAuth2 token.

Used by the usage tracking middleware to tag each public API event with the
publisher that owns the OAuth2 application the consumer is using.
"""

from __future__ import annotations

from django.core.cache import cache

_CACHE_ATTR = "_usage_tracking_resolved_publisher"
_REDIS_CACHE_TTL = 300  # 5 minutes


def resolve_publisher_from_request(request) -> tuple[int | None, str | None]:
    """Return ``(publisher_id, publisher_slug)`` for the request, or ``(None, None)``.

    Resolution order:
      1. In-request memo (avoids duplicate calls within the same request)
      2. Redis cache keyed by access_token.pk (avoids repeated DB lookups)
      3. DB lookup via access_token → application → owner → PublisherMember

    ``request.access_token`` must be set by OAuth2Auth before this is called.
    """
    cached = getattr(request, _CACHE_ATTR, None)
    if cached is not None:
        return cached

    result = _resolve(request)
    try:
        setattr(request, _CACHE_ATTR, result)
    except (AttributeError, TypeError):
        pass
    return result


def _resolve(request) -> tuple[int | None, str | None]:
    token = getattr(request, "access_token", None)
    if token is None:
        return None, None

    token_pk = getattr(token, "pk", None)
    if token_pk is not None:
        redis_key = f"pub_resolver:token:{token_pk}"
        cached = cache.get(redis_key)
        if cached is not None:
            return tuple(cached)

    application = getattr(token, "application", None)
    if application is None:
        return None, None

    owner = getattr(application, "user", None)
    if owner is None:
        return None, None

    result = _lookup_publisher_for_user(owner)

    if token_pk is not None:
        cache.set(redis_key, list(result), _REDIS_CACHE_TTL)

    return result


def _lookup_publisher_for_user(owner) -> tuple[int | None, str | None]:
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
        return None, None
    return membership.publisher_id, membership.publisher.slug
