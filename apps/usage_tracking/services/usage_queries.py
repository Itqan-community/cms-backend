"""High-level usage query helpers backed by Mixpanel Segmentation API.

Thin wrappers over ``MixpanelSegmentationClient`` that apply publisher
filtering and shape responses for portal endpoints. Redis caching is
handled at the endpoint layer (per CLAUDE.md KISS: one concern per layer).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.usage_tracking.services.mixpanel_client import MixpanelSegmentationClient

EVENT_NAME = "public_api_request"


def _build_client() -> MixpanelSegmentationClient:
    return MixpanelSegmentationClient(
        api_base=settings.MIXPANEL_API_BASE,
        project_id=settings.MIXPANEL_PROJECT_ID,
        service_username=settings.MIXPANEL_SERVICE_USERNAME,
        service_secret=settings.MIXPANEL_SERVICE_SECRET,
    )


def _publisher_where(publisher_id: int | None) -> str | None:
    if publisher_id is None:
        return None
    return f'properties["publisher_id"] == {int(publisher_id)}'


def get_timeseries(
    from_date: str,
    to_date: str,
    publisher_id: int | None,
    client: MixpanelSegmentationClient | None = None,
) -> dict[str, Any]:
    client = client or _build_client()
    return client.query(
        event=EVENT_NAME,
        from_date=from_date,
        to_date=to_date,
        where=_publisher_where(publisher_id),
    )


def get_top_endpoints(
    from_date: str,
    to_date: str,
    publisher_id: int | None,
    client: MixpanelSegmentationClient | None = None,
) -> dict[str, Any]:
    client = client or _build_client()
    return client.query(
        event=EVENT_NAME,
        from_date=from_date,
        to_date=to_date,
        where=_publisher_where(publisher_id),
        on='properties["endpoint"]',
    )


def get_top_entities(
    from_date: str,
    to_date: str,
    publisher_id: int | None,
    client: MixpanelSegmentationClient | None = None,
) -> dict[str, Any]:
    client = client or _build_client()
    return client.query(
        event=EVENT_NAME,
        from_date=from_date,
        to_date=to_date,
        where=_publisher_where(publisher_id),
        on='properties["entity_ids"]',
    )
