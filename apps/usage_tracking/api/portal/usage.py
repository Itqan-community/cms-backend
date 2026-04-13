"""Portal endpoints for publisher-facing API usage dashboards."""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from ninja import Query
from ninja.errors import HttpError

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import PublisherMember
from apps.usage_tracking.services import usage_queries

router = ItqanRouter(tags=[NinjaTag.USAGE])

CACHE_KEY_TEMPLATE = "usage:{kind}:{publisher_id}:{from_date}:{to_date}"


def _resolve_publisher_id(request: Request, requested_publisher_id: int | None) -> int | None:
    """Staff see any publisher; non-staff are scoped to their own publisher.

    Raises 403 if a non-staff user asks for a publisher they don't own.
    """
    user = request.user
    if not getattr(user, "is_authenticated", False):
        raise HttpError(401, "Authentication required")
    if user.is_staff:
        return requested_publisher_id

    membership = (
        PublisherMember.objects.filter(user=user).select_related("publisher").first()
    )
    if membership is None:
        raise HttpError(403, "No publisher membership")

    if requested_publisher_id is not None and requested_publisher_id != membership.publisher_id:
        raise HttpError(403, "Cannot access another publisher's usage")

    return membership.publisher_id


def _validate_dates(from_date: str, to_date: str) -> None:
    try:
        datetime.strptime(from_date, "%Y-%m-%d")
        datetime.strptime(to_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HttpError(400, "Dates must be YYYY-MM-DD") from exc


def _cached(kind: str, publisher_id: int | None, from_date: str, to_date: str, loader):
    key = CACHE_KEY_TEMPLATE.format(
        kind=kind,
        publisher_id=publisher_id if publisher_id is not None else "all",
        from_date=from_date,
        to_date=to_date,
    )
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = loader()
    cache.set(key, result, settings.USAGE_TRACKING_CACHE_TTL)
    return result


@router.get("usage/timeseries/", description="API usage counts over time")
def get_usage_timeseries(
    request: Request,
    from_date: str = Query(...),
    to_date: str = Query(...),
    publisher_id: int | None = Query(None),
):
    _validate_dates(from_date, to_date)
    resolved = _resolve_publisher_id(request, publisher_id)
    return _cached(
        "timeseries",
        resolved,
        from_date,
        to_date,
        lambda: usage_queries.get_timeseries(from_date, to_date, resolved),
    )


@router.get("usage/top-endpoints/", description="Most-hit endpoints in a window")
def get_usage_top_endpoints(
    request: Request,
    from_date: str = Query(...),
    to_date: str = Query(...),
    publisher_id: int | None = Query(None),
):
    _validate_dates(from_date, to_date)
    resolved = _resolve_publisher_id(request, publisher_id)
    return _cached(
        "top-endpoints",
        resolved,
        from_date,
        to_date,
        lambda: usage_queries.get_top_endpoints(from_date, to_date, resolved),
    )


@router.get("usage/top-entities/", description="Most-requested entity IDs in a window")
def get_usage_top_entities(
    request: Request,
    from_date: str = Query(...),
    to_date: str = Query(...),
    publisher_id: int | None = Query(None),
):
    _validate_dates(from_date, to_date)
    resolved = _resolve_publisher_id(request, publisher_id)
    return _cached(
        "top-entities",
        resolved,
        from_date,
        to_date,
        lambda: usage_queries.get_top_entities(from_date, to_date, resolved),
    )
