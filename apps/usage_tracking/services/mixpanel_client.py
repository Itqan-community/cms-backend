from __future__ import annotations

import itertools
import logging
import math
from typing import Any

from mixpanel import BufferedConsumer, Consumer, Mixpanel
import requests

logger = logging.getLogger(__name__)

_IMPORT_CHUNK_SIZE = 2000
_REQUEST_TIMEOUT_SECONDS = 30


class MixpanelIngestClient:
    """Sends events to Mixpanel, real-time via `track` or historical via `import_events`"""

    def __init__(self, token: str, ingest_host: str, enabled: bool, project_id: str = "") -> None:
        self._token = token
        self._ingest_host = ingest_host
        self._enabled = enabled
        self._project_id = project_id
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

    def import_events(self, events: list[dict[str, Any]]) -> int:
        """POST `events` to `/import` in chunks, returning the total records imported.

        Unlike `track`, `/import` accepts a fixed historical `time` per event and dedups
        on `$insert_id` -- the right tool for batch jobs that may rerun or retry over the
        same time window (see the CF audio-usage sync).

        Each event dict must already be in Mixpanel's import shape: `{"event": ...,
        "properties": {"time": ..., "distinct_id": ..., "$insert_id": ..., ...}}`.
        No-ops (returns 0) when disabled, no token, or `events` is empty.
        """
        if not self._enabled or not self._token or not events:
            logger.info("MixpanelIngestClient: import no-op (enabled=%s, events=%d)", self._enabled, len(events))
            return 0

        url = f"https://{self._ingest_host}/import"
        total_imported = 0
        num_chunks = math.ceil(len(events) / _IMPORT_CHUNK_SIZE)
        logger.info(
            "MixpanelIngestClient: importing %d event(s) in %d chunk(s) to %s project_id=%s",
            len(events),
            num_chunks,
            url,
            self._project_id,
        )
        for chunk_index, chunk in enumerate(itertools.batched(events, _IMPORT_CHUNK_SIZE, strict=False)):
            response = requests.post(
                url,
                params={"strict": "1", "project_id": self._project_id},
                json=list(chunk),
                auth=(self._token, ""),
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            # `strict=1` returns validation failures in the body with a 400; surface it
            # so a rejected batch is traceable instead of a bare HTTPError.
            if response.status_code >= 400:
                logger.error(
                    "MixpanelIngestClient: /import returned %d for chunk %d: %.500s",
                    response.status_code,
                    chunk_index,
                    response.text,
                )

            response.raise_for_status()
            body = response.json()
            imported = body.get("num_records_imported", 0)
            total_imported += imported
            logger.info(
                "MixpanelIngestClient: chunk %d imported %d/%d (status=%s)",
                chunk_index,
                imported,
                len(chunk),
                body.get("status"),
            )

        logger.info("MixpanelIngestClient: total imported %d/%d event(s)", total_imported, len(events))
        return total_imported
