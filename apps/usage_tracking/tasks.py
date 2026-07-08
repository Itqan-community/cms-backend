"""Celery tasks for usage tracking."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
import functools
import json
import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.db import connections
import redis
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

logger = logging.getLogger(__name__)

_TRANSIENT_ERRORS = (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)

TRACKING_BUFFER_KEY = "usage_tracking:tracking_buffer"
_TRACKING_INFLIGHT_KEY = "usage_tracking:tracking_buffer:inflight"
# Separate Redis DB from the Django cache (DB 1) to avoid eviction by cache policies.
_TRACKING_REDIS_DB = 2


class UnexpectedDatabaseQuery(AssertionError):
    """Raised when code wrapped in :func:`no_db_queries` issues a database query."""


@contextmanager
def no_db_queries() -> Iterator[None]:
    """Forbid any database query within the block, on every configured connection.

    Usage-tracking work runs off the request and must resolve all data at the call
    site, so a stray ORM access here would be an unintended round trip. Any query
    raises :class:`UnexpectedDatabaseQuery`.
    """

    def _blocker(execute, sql, params, many, context):
        raise UnexpectedDatabaseQuery(f"Unexpected database query in no_db_queries block: {sql}")

    with ExitStack() as stack:
        for connection in connections.all():
            stack.enter_context(connection.execute_wrapper(_blocker))
        yield


def no_db_queries_task(func: Callable) -> Callable:
    """Run the wrapped task body under :func:`no_db_queries`."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with no_db_queries():
            return func(*args, **kwargs)

    return wrapper


def _build_ingest_client() -> MixpanelIngestClient:
    return MixpanelIngestClient(
        token=settings.MIXPANEL_PROJECT_TOKEN,
        ingest_host=settings.MIXPANEL_INGEST_HOST,
        enabled=settings.MIXPANEL_ENABLED,
    )


# Sentinel distinguishing "not resolved yet" from a resolved-to-None client (no Redis,
# e.g. dev's LocMemCache), so we resolve at most once instead of on every call.
_UNSET = object()
_tracking_redis_client: redis.Redis | None | object = _UNSET


def _build_tracking_redis() -> redis.Redis | None:
    """Build the tracking-buffer Redis client, or ``None`` when no Redis is available.

    Connection details reuse the ``default`` cache's django-redis connection (host, port,
    auth, TLS, socket opts), then swap to a dedicated DB so cache eviction policies cannot
    drop buffered events.

    Returns ``None`` when the cache backend is not django-redis (e.g. dev's LocMemCache):
    callers treat that as tracking disabled, so dev needs no Redis running.
    """
    try:
        from django_redis import get_redis_connection

        cache_conn = get_redis_connection("default")
    except (ImportError, NotImplementedError):
        # ImportError: django-redis absent. NotImplementedError: get_redis_connection on a
        # non-django-redis backend (LocMemCache in dev). Either way, no Redis to reuse.
        return None

    kwargs = dict(cache_conn.connection_pool.connection_kwargs)
    kwargs["db"] = _TRACKING_REDIS_DB
    kwargs.setdefault("socket_connect_timeout", 1)
    kwargs.setdefault("socket_timeout", 1)
    kwargs["decode_responses"] = True
    return redis.Redis(**kwargs)


def _get_tracking_redis() -> redis.Redis | None:
    """Return the module-level tracking-buffer Redis client, or ``None`` when unavailable.

    Lazy-initialised (settings must be loaded) and resolved once; see
    :func:`_build_tracking_redis` for how the connection is derived.
    """
    global _tracking_redis_client
    if _tracking_redis_client is _UNSET:
        _tracking_redis_client = _build_tracking_redis()
    return _tracking_redis_client


@shared_task(
    bind=True,
    autoretry_for=_TRANSIENT_ERRORS,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    acks_late=True,
    ignore_result=True,
)
@no_db_queries_task
def track_api_request_task(
    self,
    distinct_id: str,
    event: str,
    properties: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> None:
    if not distinct_id:
        return

    # The accessed entity's name is resolved at the call site (within the request, where
    # the entity is already loaded) so this task never needs to touch the database.
    client = _build_ingest_client()
    client.track(distinct_id, event, properties, meta=meta)


@shared_task(ignore_result=True)
@no_db_queries_task
def flush_tracking_buffer_task() -> None:
    """Drain the Redis tracking buffer and send all queued events to Mixpanel in one batch.

    Uses RENAME to atomically move the live buffer to an inflight key before reading,
    so concurrent requests keep writing to a fresh buffer and a crash between read and
    delete cannot cause double-processing of the same batch on the next flush.
    """
    r = _get_tracking_redis()
    if r is None:
        return  # no Redis available (e.g. dev/LocMemCache); tracking disabled

    # Atomically claim the current buffer. If the key doesn't exist, RENAME raises
    # ResponseError -- treat that as empty buffer.
    try:
        r.rename(TRACKING_BUFFER_KEY, _TRACKING_INFLIGHT_KEY)
    except redis.ResponseError:
        return  # buffer was empty

    raw_items: list[str] = r.lrange(_TRACKING_INFLIGHT_KEY, 0, -1)

    if not raw_items:
        r.delete(_TRACKING_INFLIGHT_KEY)
        return

    events: list[dict[str, Any]] = []
    for raw in raw_items:
        try:
            events.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning("flush_tracking_buffer_task: skipping malformed event: %.120s", raw)

    # Send then delete in finally so inflight is always cleaned up. A network failure
    # during track_batch logs and drops the batch -- analytics loss is acceptable and
    # leaving inflight would not help (next RENAME silently overwrites it anyway).
    try:
        if events:
            client = _build_ingest_client()
            client.track_batch(events)
            logger.info("flush_tracking_buffer_task: sent %d events to Mixpanel", len(events))
    finally:
        r.delete(_TRACKING_INFLIGHT_KEY)
