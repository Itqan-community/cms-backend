"""Per-endpoint usage tracking decorator for public ninja API functions.

Replaces the old global ``UsageTrackingMiddleware``. Apply ``@track_usage()`` to a
public endpoint to dispatch a Mixpanel tracking task after the view returns.

Entity ids/names (and optionally publisher) are extracted from the **served** objects
-- the decorator reads the paginated ``{"items": [...]}`` result, so it sees exactly the
page returned after search/ordering/pagination, not the full filtered set. The endpoint
can enrich or override the event by calling :func:`track_extra` from inside the view;
publisher is recorded per-served-object because the publisher of a served asset can only
be known *after* the asset is fetched (it is a property of the Asset, not of the
requesting user).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import logging
import time
from typing import Any
from urllib.parse import parse_qs
import uuid

from django.core.cache import cache

from apps.usage_tracking.tasks import track_api_request_task

logger = logging.getLogger(__name__)

DEFAULT_EVENT = "public_api_request"

# Upper bound on entity id/name lists pushed onto an event, to keep property payloads
# bounded. Mirrors the public ninja MAX_PAGE_SIZE.
MAX_ENTITY_IDS = 1000

_EXTRA_ATTR = "_usage_tracking_extra"

_KNOWN_FILTER_KEYS = ("reciter_id", "riwayah_id", "qiraah_id")

# reciter_id is recorded as a filter property; reciters are few and rarely change, so we
# also resolve a human-readable name and cache it to keep this off the hot path.
_RECITER_NAME_CACHE_KEY = "usage_tracking:reciter_name:{id}"
_RECITER_NAME_CACHE_TTL = 60 * 60  # 1 hour


def track_extra(request, **props: Any) -> None:
    """Merge custom Mixpanel properties from inside a tracked view.

    The decorator seeds an empty dict on the request before calling the view; this
    helper updates it. Values set here take precedence over the decorator's
    auto-extracted entity/publisher properties. Call it as many times as needed.
    """
    bucket = getattr(request, _EXTRA_ATTR, None)
    if bucket is None:
        bucket = {}
        try:
            setattr(request, _EXTRA_ATTR, bucket)
        except (AttributeError, TypeError):
            return
    bucket.update(props)


def track_usage(
    *,
    event: str = DEFAULT_EVENT,
    entity_type: str | None = None,
    publisher_from: str | None = None,
) -> Callable:
    """Decorate a public ninja endpoint to dispatch a usage-tracking event.

    Place directly under ``@router.get(...)`` and above ``@paginate`` so it wraps the
    whole pagination/ordering/searching chain and observes the served page::

        @router.get("recitations/", response=list[RecitationListOut])
        @track_usage(entity_type="recitation", publisher_from="publisher")
        @paginate
        def list_recitations(request, ...):
            ...

    Args:
        event: Mixpanel event name.
        entity_type: recorded as ``entity_type`` on the event (e.g. ``"recitation"``).
        publisher_from: name of the relation/attribute on each served object that holds
            its owning ``Publisher`` (e.g. ``"publisher"``). When set, the decorator
            records distinct ``publisher_ids``/``publisher_names`` for the served page.
            Leave ``None`` for endpoints whose rows aren't publisher-scoped
            (reciters/, riwayahs/).

    Entity ids/names are extracted from the served objects (``id`` and ``name``). The
    view may override any of these via :func:`track_extra`. On a raised exception the
    error propagates and **no** event is dispatched.
    """

    def wrapper(view: Callable) -> Callable:
        @wraps(view)
        def tracked(request, *args: Any, **kwargs: Any) -> Any:
            setattr(request, _EXTRA_ATTR, {})
            start = time.monotonic()
            result = view(request, *args, **kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                _dispatch(
                    request,
                    result,
                    event=event,
                    entity_type=entity_type,
                    publisher_from=publisher_from,
                    latency_ms=latency_ms,
                )
            except Exception:
                logger.exception("usage_tracking decorator dispatch failed")
            return result

        return tracked

    return wrapper


# The page-slice key produced by the project's NinjaPagination
# (apps/core/ninja_utils/paginations.py).
_PAGINATION_KEY = "results"


def _served_objects(result: Any) -> list:
    """Return the served model objects from a view's return value.

    Handles paginated ``{"results": [...]}`` dicts, raw lists/querysets, and single
    objects. The slice is one page, so materializing it here is cheap.
    """
    if isinstance(result, dict):
        page = result.get(_PAGINATION_KEY)
        return list(page) if page is not None else []
    if isinstance(result, list):
        return result
    if result is None:
        return []
    # Querysets and other iterables of objects.
    try:
        return list(result)
    except TypeError:
        return [result]


def _extract_entities(objects: list) -> tuple[list, list]:
    ids: list = []
    names: list = []
    for obj in objects[:MAX_ENTITY_IDS]:
        obj_id = getattr(obj, "id", None)
        if obj_id is None:
            continue
        ids.append(obj_id)
        names.append(getattr(obj, "name", "") or "")
    return ids, names


def _extract_publishers(objects: list, publisher_from: str) -> tuple[list, list]:
    ids: list = []
    names: list = []
    seen: set = set()
    for obj in objects:
        pub_id = getattr(obj, f"{publisher_from}_id", None)
        if pub_id is None or pub_id in seen:
            continue
        seen.add(pub_id)
        ids.append(pub_id)
        publisher = getattr(obj, publisher_from, None)
        names.append(getattr(publisher, "name", "") or "" if publisher is not None else "")
    return ids, names


def _dispatch(
    request,
    result: Any,
    *,
    event: str,
    entity_type: str | None,
    publisher_from: str | None,
    latency_ms: int,
) -> None:
    application_id, application_name = _resolve_application(request)
    query_string = request.META.get("QUERY_STRING") or None

    objects = _served_objects(result)
    entity_ids, entity_names = _extract_entities(objects)
    publisher_ids: list = []
    publisher_names: list = []
    if publisher_from:
        publisher_ids, publisher_names = _extract_publishers(objects, publisher_from)

    parsed_qs = _parse_query_params(query_string or "")

    properties = {
        "method": request.method,
        "path": request.path,
        "endpoint": f"{request.method} {request.path}",
        "status_code": 200,
        "latency_ms": latency_ms,
        "application_id": application_id,
        "application_name": application_name,
        "auth_method": _detect_auth_method(request),
        "user_agent": request.headers.get("user-agent") or None,
        "entity_type": entity_type,
        "entity_ids": entity_ids,
        "entity_names": entity_names,
        "publisher_ids": publisher_ids,
        "publisher_names": publisher_names,
        "query_string": query_string,
        **parsed_qs,
        # View-supplied props win over auto-extracted ones.
        **(getattr(request, _EXTRA_ATTR, {}) or {}),
    }

    # The reciter_id filter is opaque; add human-readable names (cached) for Mixpanel.
    # reciter_id is a repeatable list filter (?reciter_id=1&reciter_id=2), so resolve a
    # name for every id passed. filter_reciter_name (first id) is kept for back-compat.
    reciter_ids = _parsed_reciter_ids(query_string or "")
    if reciter_ids:
        names = _resolve_reciter_names(reciter_ids)
        properties["filter_reciter_names"] = names
        properties["filter_reciter_name"] = names[0]

    ip = _client_ip(request)
    if ip:
        # Mixpanel resolves geo from $ip on ingest and does not store the raw IP.
        properties["$ip"] = ip

    track_api_request_task.delay(
        distinct_id=_distinct_id(request),
        event=event,
        properties=properties,
        meta={},
    )


def _parsed_reciter_ids(query_string: str) -> list[int]:
    """Return all integer ``reciter_id`` values from the query string, de-duplicated and
    order-preserving. ``reciter_id`` is a repeatable list filter on the public API."""
    if not query_string:
        return []
    raw = parse_qs(query_string, keep_blank_values=False).get("reciter_id", [])
    ids: list[int] = []
    seen: set[int] = set()
    for value in raw:
        try:
            reciter_id = int(value)
        except (TypeError, ValueError):
            continue
        if reciter_id not in seen:
            seen.add(reciter_id)
            ids.append(reciter_id)
    return ids


def _resolve_reciter_name(reciter_id: int) -> str | None:
    """Return a reciter's name for the given id, cached (reciters are few/stable).

    A missing reciter caches ``""`` to avoid hammering the DB on bad ids; returns
    ``None`` in that case.
    """
    key = _RECITER_NAME_CACHE_KEY.format(id=reciter_id)
    cached = cache.get(key)
    if cached is not None:
        return cached or None

    from apps.content.models import Reciter

    row = Reciter.objects.filter(pk=reciter_id).values("name_ar", "name_en").first()
    name = _prefer_arabic_name(row) if row else ""
    cache.set(key, name, _RECITER_NAME_CACHE_TTL)
    return name or None


def _resolve_reciter_names(reciter_ids: list[int]) -> list[str | None]:
    """Resolve a list of reciter ids to names (same order), reading cache first and
    fetching only the misses in a single query. A missing reciter resolves to ``None``."""
    names: dict[int, str | None] = {}
    misses: list[int] = []
    for reciter_id in reciter_ids:
        cached = cache.get(_RECITER_NAME_CACHE_KEY.format(id=reciter_id))
        if cached is not None:
            names[reciter_id] = cached or None
        else:
            misses.append(reciter_id)

    if misses:
        from apps.content.models import Reciter

        fetched = {
            row["pk"]: _prefer_arabic_name(row)
            for row in Reciter.objects.filter(pk__in=misses).values("pk", "name_ar", "name_en")
        }
        for reciter_id in misses:
            name = fetched.get(reciter_id, "")
            cache.set(_RECITER_NAME_CACHE_KEY.format(id=reciter_id), name, _RECITER_NAME_CACHE_TTL)
            names[reciter_id] = name or None

    return [names[reciter_id] for reciter_id in reciter_ids]


def _prefer_arabic_name(row: dict) -> str:
    """Pick a reciter's display name, prioritizing Arabic and falling back to English.

    Reciter ``name`` is a django-modeltranslation field, so the active-language value is
    non-deterministic on the Celery worker. We read the explicit ``name_ar``/``name_en``
    columns and prefer Arabic, since these names feed Mixpanel for an Arabic-first audience.
    """
    return (row.get("name_ar") or "") or (row.get("name_en") or "")


def _resolve_application(request) -> tuple[int | None, str | None]:
    """Return (application_id, application_name) for OAuth2-authed requests."""
    token = getattr(request, "access_token", None)
    if token is None:
        return None, None
    application = getattr(token, "application", None)
    if application is None:
        return None, None
    return getattr(application, "id", None), getattr(application, "name", None)


def _detect_auth_method(request) -> str:
    """One of: 'oauth2', 'jwt', 'session', 'anonymous'."""
    if getattr(request, "access_token", None) is not None:
        return "oauth2"
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return "anonymous"
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return "jwt"
    return "session"


def _client_ip(request) -> str | None:
    """Resolve real client IP behind nginx/cloudflare. Used for Mixpanel $ip."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 -- first entry is the real client.
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def _parse_query_params(query_string: str) -> dict:
    """Extract first-class properties from the query string.

    NOTE: query_string itself is also captured raw on the event. The public API filter
    schema does not accept any PII fields (see apps/content/api/public/*.py -- only IDs,
    page, search, ordering). If a future endpoint adds a PII-bearing query param,
    sanitize here first.
    """
    if not query_string:
        return {}
    parsed = parse_qs(query_string, keep_blank_values=False)
    result: dict = {}

    page_raw = parsed.get("page", [None])[0]
    if page_raw:
        try:
            result["page"] = int(page_raw)
        except (TypeError, ValueError):
            pass

    search = parsed.get("search", [None])[0]
    if search:
        result["search"] = search

    for key in _KNOWN_FILTER_KEYS:
        value = parsed.get(key, [None])[0]
        if value:
            try:
                result[f"filter_{key}"] = int(value)
            except (TypeError, ValueError):
                result[f"filter_{key}"] = value

    ordering = parsed.get("ordering", [None])[0]
    if ordering:
        result["ordering"] = ordering

    return result


def _distinct_id(request) -> str:
    # OAuth2 client_credentials: request.user is anonymous but the OAuth2 application is
    # the stable identity for that downstream client.
    token = getattr(request, "access_token", None)
    if token is not None:
        application = getattr(token, "application", None)
        if application is not None:
            return f"app-{application.id}"

    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return f"user-{user.pk}"

    # True anonymous -- every request gets a fresh ID. Acceptable; we have no better
    # signal. Most public-API traffic should hit one of the branches above.
    return f"anon-{uuid.uuid4().hex[:12]}"
