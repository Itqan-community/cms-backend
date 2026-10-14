"""Cloudflare GraphQL Analytics client for per-request asset download data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, TypedDict

import requests

from apps.usage_tracking.services.cf_analytics_client import CF_GRAPHQL_URL, CloudflareGraphQLError
from apps.usage_tracking.services.download_paths import ASSET_PATH_LIKE

_REQUEST_TIMEOUT_SECONDS = 30

_FILTER = """
          datetime_geq: $start
          datetime_lt: $end
          clientRequestHTTPHost: $hostname
          clientRequestPath_like: $pathLike
          requestSource: "eyeball"
"""

_RANGE_ARGS = "$zoneTag: String!, $start: Time!, $end: Time!, $hostname: String!, $pathLike: String!, $limit: Int!"

_EVENTS_QUERY = f"""
query AssetDownloadEvents({_RANGE_ARGS}) {{
  viewer {{
    zones(filter: {{ zoneTag: $zoneTag }}) {{
      httpRequestsAdaptive(limit: $limit, filter: {{ {_FILTER} }}, orderBy: [datetime_ASC]) {{
        datetime
        rayName
        clientRequestPath
        clientCountryName
        edgeResponseStatus
        clientIP
      }}
    }}
  }}
}}
"""

_TOTALS_QUERY = f"""
query AssetDownloadTotals({_RANGE_ARGS}) {{
  viewer {{
    zones(filter: {{ zoneTag: $zoneTag }}) {{
      httpRequestsAdaptiveGroups(limit: $limit, filter: {{ {_FILTER} }}) {{
        count
        avg {{ sampleInterval }}
        sum {{ edgeResponseBytes }}
        dimensions {{
          clientRequestPath
          clientCountryName
          edgeResponseStatus
        }}
      }}
    }}
  }}
}}
"""

_LIMITS_QUERY = """
query AssetDownloadLimits($zoneTag: String!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      settings { httpRequestsAdaptive { maxPageSize notOlderThan } }
    }
  }
}
"""


class CFDownloadEvent(TypedDict):
    datetime: str
    rayName: str
    clientRequestPath: str
    clientCountryName: str
    edgeResponseStatus: int
    clientIP: str


class CFDownloadTotalDimensions(TypedDict):
    clientRequestPath: str
    clientCountryName: str
    edgeResponseStatus: int


class CFDownloadTotal(TypedDict):
    count: int
    avg: dict[str, float]
    sum: dict[str, int]
    dimensions: CFDownloadTotalDimensions


@dataclass(frozen=True, slots=True)
class DatasetLimits:
    max_page_size: int
    not_older_than: timedelta


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class CloudflareDownloadsClient:
    """Reads asset-file requests for one hostname. `start` is inclusive, `end` exclusive (UTC)."""

    def __init__(self, zone_tag: str, api_token: str, hostname: str) -> None:
        self._zone_tag = zone_tag
        self._api_token = api_token
        self._hostname = hostname

    def fetch_limits(self) -> DatasetLimits:
        zone = self._zone(_LIMITS_QUERY, {"zoneTag": self._zone_tag})
        dataset = zone["settings"]["httpRequestsAdaptive"]
        return DatasetLimits(
            max_page_size=int(dataset["maxPageSize"]),
            not_older_than=timedelta(seconds=int(dataset["notOlderThan"])),
        )

    def fetch_events(self, start: datetime, end: datetime, limit: int) -> list[CFDownloadEvent]:
        return self._zone(_EVENTS_QUERY, self._range_variables(start, end, limit))["httpRequestsAdaptive"]

    def fetch_totals(self, start: datetime, end: datetime, limit: int) -> list[CFDownloadTotal]:
        return self._zone(_TOTALS_QUERY, self._range_variables(start, end, limit))["httpRequestsAdaptiveGroups"]

    def _range_variables(self, start: datetime, end: datetime, limit: int) -> dict[str, Any]:
        return {
            "zoneTag": self._zone_tag,
            "start": _format_time(start),
            "end": _format_time(end),
            "hostname": self._hostname,
            "pathLike": ASSET_PATH_LIKE,
            "limit": limit,
        }

    def _zone(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            CF_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("errors"):
            raise CloudflareGraphQLError(str(payload["errors"]))
        zones = ((payload.get("data") or {}).get("viewer") or {}).get("zones") or []
        if not zones:
            raise CloudflareGraphQLError(f"no zone matched zoneTag={self._zone_tag} (check CF_ZONE_ID/token scope)")
        return zones[0]
