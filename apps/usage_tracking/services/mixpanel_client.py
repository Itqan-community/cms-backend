from __future__ import annotations

from typing import Any

from mixpanel import BufferedConsumer, Consumer, Mixpanel


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

    def track_batch(self, events: list[dict[str, Any]]) -> None:
        """Send a batch of pre-serialized events in a single HTTP call.

        Each event dict must have keys: distinct_id, event, properties, meta.
        No-ops when disabled, empty list, or no token.
        """
        if not self._enabled or not self._token or not events:
            return
        consumer = BufferedConsumer(max_size=len(events), api_host=self._ingest_host)
        sdk = Mixpanel(self._token, consumer=consumer)
        for item in events:
            sdk.track(
                item["distinct_id"],
                item["event"],
                item.get("properties", {}),
                meta=item.get("meta"),
            )
        consumer.flush()
