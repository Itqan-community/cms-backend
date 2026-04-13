"""Resolve a request's publisher identity from its OAuth2 token.

Used by the usage tracking middleware to tag each public API event with the
publisher that owns the OAuth2 application the consumer is using.
"""

from __future__ import annotations

_CACHE_ATTR = "_usage_tracking_resolved_publisher"


def resolve_publisher_from_request(request) -> tuple[int | None, str | None]:
    """Return ``(publisher_id, publisher_slug)`` for the request, or ``(None, None)``.

    Resolution order:
      1. ``request.access_token`` (set by ``OAuth2ExtraTokenMiddleware``)
      2. ``access_token.application.user`` -> the OAuth2 app owner
      3. The owner's ``PublisherMember`` (OWNER role preferred)

    Result is memoised on the request to avoid duplicate DB queries when the
    middleware and downstream code both need the publisher.
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

    application = getattr(token, "application", None)
    if application is None:
        return None, None

    owner = getattr(application, "user", None)
    if owner is None:
        return None, None

    return _lookup_publisher_for_user(owner)


def _lookup_publisher_for_user(owner) -> tuple[int | None, str | None]:
    """Database lookup, isolated for easy mocking in unit tests."""
    from apps.publishers.models import PublisherMember

    membership = (
        PublisherMember.objects.filter(user=owner, role=PublisherMember.RoleChoice.OWNER)
        .select_related("publisher")
        .first()
    )
    if membership is None:
        membership = (
            PublisherMember.objects.filter(user=owner)
            .select_related("publisher")
            .first()
        )
    if membership is None:
        return None, None
    return membership.publisher_id, membership.publisher.slug
