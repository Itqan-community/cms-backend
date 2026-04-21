"""Mixpanel ingest (SDK) and segmentation (REST) clients."""

from __future__ import annotations

from typing import Any

from mixpanel import Consumer, Mixpanel
import requests
from requests.auth import HTTPBasicAuth


class MixpanelQueryError(Exception):
    """Raised when a Mixpanel query API call returns a non-2xx response."""


class MixpanelIngestClient:
    def __init__(self, token: str, ingest_host: str, enabled: bool) -> None:
        self._token = token
        self._ingest_host = ingest_host
        self._enabled = enabled
        self._sdk: Mixpanel | None = None

    def track(self, distinct_id: str, event: str, properties: dict[str, Any]) -> None:
        if not self._enabled or not self._token:
            return
        if self._sdk is None:
            self._sdk = Mixpanel(self._token, consumer=Consumer(api_host=self._ingest_host))
        self._sdk.track(distinct_id, event, properties)


class MixpanelSegmentationClient:
    def __init__(
        self,
        api_base: str,
        project_id: str,
        service_username: str,
        service_secret: str,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._project_id = project_id
        self._auth = HTTPBasicAuth(service_username, service_secret)

    def query(
        self,
        event: str,
        from_date: str,
        to_date: str,
        where: str | None = None,
        on: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "project_id": self._project_id,
        }
        if where is not None:
            params["where"] = where
        if on is not None:
            params["on"] = on

        response = requests.get(
            f"{self._api_base}/api/2.0/segmentation",
            params=params,
            auth=self._auth,
            timeout=30,
        )
        if not response.ok:
            # Deliberately omit response.text — Mixpanel error bodies can echo
            # credentials or project identifiers that would leak into Sentry.
            raise MixpanelQueryError(f"Mixpanel segmentation query failed: HTTP {response.status_code}")
        return response.json()
