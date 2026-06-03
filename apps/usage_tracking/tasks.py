"""Celery tasks for usage tracking."""

from __future__ import annotations

from typing import Any

from celery import shared_task
from django.conf import settings
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout as RequestsTimeout

from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

_TRANSIENT_ERRORS = (RequestsConnectionError, RequestsTimeout, ConnectionError, TimeoutError)


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
def track_api_request_task(
    self,
    distinct_id: str,
    event: str,
    properties: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> None:
    if not distinct_id:
        return

    accessed_entity_id = properties.get("accessed_entity_id")
    if accessed_entity_id is not None:
        from apps.content.models import Asset

        row = Asset.objects.filter(pk=accessed_entity_id).values("name").first()
        properties = {**properties, "accessed_entity_name": row["name"] if row else None}
    client = _build_ingest_client()
    client.track(distinct_id, event, properties, meta=meta)
