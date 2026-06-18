"""Celery tasks for usage tracking."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
import functools
from typing import Any

from celery import shared_task
from django.conf import settings
from django.db import connections
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

_TRANSIENT_ERRORS = (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)


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
