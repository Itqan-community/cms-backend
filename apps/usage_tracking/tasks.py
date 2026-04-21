"""Celery tasks for usage tracking."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from django.conf import settings
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

_TRANSIENT_ERRORS = (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)


def _build_ingest_clients() -> list[MixpanelIngestClient]:
    tokens = [
        settings.MIXPANEL_PROJECT_TOKEN,
        settings.MIXPANEL_PROJECT_TOKEN_2,
        settings.MIXPANEL_PROJECT_TOKEN_3,
        settings.MIXPANEL_PROJECT_TOKEN_4,
    ]
    return [
        MixpanelIngestClient(
            token=token,
            ingest_host=settings.MIXPANEL_INGEST_HOST,
            enabled=settings.MIXPANEL_ENABLED,
        )
        for token in tokens
        if token
    ]


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
def track_api_request_task(
    self,
    distinct_id: str,
    event: str,
    properties: dict[str, Any],
) -> None:
    if not distinct_id:
        return
    for client in _build_ingest_clients():
        client.track(distinct_id, event, properties)
