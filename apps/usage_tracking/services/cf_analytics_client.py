"""Cloudflare GraphQL Analytics client for R2 audio (.mp3) edge usage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, TypedDict

import requests

logger = logging.getLogger(__name__)

CF_GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"

_REQUEST_TIMEOUT_SECONDS = 30

_QUERY = """
query AudioHTTPUsage($zoneTag: String!, $start: Time!, $end: Time!, $hostname: String!, $pathLike: String!, $source: String!, $limit: Int!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      httpRequestsAdaptiveGroups(
        limit: $limit
        filter: {
          datetime_geq: $start
          datetime_lt: $end
          clientRequestHTTPHost: $hostname
          clientRequestPath_like: $pathLike
          requestSource: $source
        }
        orderBy: [count_DESC]
      ) {
        count
        dimensions {
          clientRequestPath
          clientCountryName
          clientDeviceType
          edgeResponseStatus
          cacheStatus
        }
        sum {
          edgeResponseBytes
        }
      }
    }
  }
}
"""


class CFUsageRowDimensions(TypedDict):
    clientRequestPath: str
    clientCountryName: str
    clientDeviceType: str
    edgeResponseStatus: int
    cacheStatus: str


class CFUsageRowSum(TypedDict):
    edgeResponseBytes: int


class CFUsageRow(TypedDict):
    count: int
    dimensions: CFUsageRowDimensions
    sum: CFUsageRowSum


class CloudflareGraphQLError(RuntimeError):
    """Raised when the Cloudflare GraphQL API returns an ``errors`` payload."""


@dataclass(frozen=True, slots=True)
class CFUsageResult:
    rows: list[CFUsageRow]
    truncated: bool  # len(rows) >= limit


class CloudflareAnalyticsClient:
    """Fetches `.mp3` edge-request usage from Cloudflare's GraphQL Analytics API."""

    def __init__(self, zone_tag: str, api_token: str, limit: int = 10000) -> None:
        self._zone_tag = zone_tag
        self._api_token = api_token
        self._limit = limit

    def fetch_audio_usage(self, hostname: str, start: datetime, end: datetime) -> CFUsageResult:
        """Return `.mp3` eyeball-request rows for ``hostname`` within ``[start, end)``.

        ``start``/``end`` must be timezone-aware UTC. Raises ``CloudflareGraphQLError``
        if the API reports GraphQL errors. ``CFUsageResult.truncated`` tells the caller
        whether the result hit the query limit, since deciding how to react (log,
        re-slice the window) is an orchestration concern, not a client one.
        """
        variables = {
            "zoneTag": self._zone_tag,
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hostname": hostname,
            "pathLike": "%.mp3",
            "source": "eyeball",
            "limit": self._limit,
        }

        logger.info(
            "CloudflareAnalyticsClient: querying zone=%s host=%s window=[%s, %s) pathLike=%s source=%s limit=%d",
            self._zone_tag,
            hostname,
            variables["start"],
            variables["end"],
            variables["pathLike"],
            variables["source"],
            self._limit,
        )
        response = requests.post(
            CF_GRAPHQL_URL,
            json={"query": _QUERY, "variables": variables},
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()

        if payload.get("errors"):
            logger.error("CloudflareAnalyticsClient: GraphQL errors: %s", payload["errors"])
            raise CloudflareGraphQLError(str(payload["errors"]))

        zones = ((payload.get("data") or {}).get("viewer") or {}).get("zones") or []
        if not zones:
            logger.warning(
                "CloudflareAnalyticsClient: no zones matched zoneTag=%s (check CF_ZONE_ID/token scope)",
                self._zone_tag,
            )
            return CFUsageResult(rows=[], truncated=False)
        rows = zones[0]["httpRequestsAdaptiveGroups"]
        logger.info("CloudflareAnalyticsClient: received %d row(s) from httpRequestsAdaptiveGroups", len(rows))
        return CFUsageResult(rows=rows, truncated=len(rows) >= self._limit)
