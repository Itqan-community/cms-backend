from __future__ import annotations

from typing import Any

from mixpanel import Consumer, Mixpanel


class MixpanelIngestClient:
    def __init__(self, token: str, ingest_host: str, enabled: bool) -> None:
        self._token = token
        self._ingest_host = ingest_host
        self._enabled = enabled
        self._sdk: Mixpanel | None = None

    def track(
        self, distinct_id: str, event: str, properties: dict[str, Any], meta: dict[str, Any] | None = None
    ) -> None:
        if not self._enabled or not self._token:
            return
        if self._sdk is None:
            self._sdk = Mixpanel(self._token, consumer=Consumer(api_host=self._ingest_host))
        self._sdk.track(distinct_id, event, properties, meta=meta)
