"""Cloudflare GraphQL client for R2 per-object reads (any access route, aggregated)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from apps.usage_tracking.services.cf_analytics_client import CF_GRAPHQL_URL, CloudflareGraphQLError

_REQUEST_TIMEOUT_SECONDS = 30
_QUERY = """
query R2ObjectReads($accountTag: String!, $bucket: String!, $start: Time!, $end: Time!, $limit: Int!) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      r2OperationsAdaptiveGroups(
        limit: $limit
        filter: { datetime_geq: $start, datetime_lt: $end, bucketName: $bucket, actionType: "GetObject" }
      ) {
        sum { requests }
        dimensions { objectName actionStatus }
      }
    }
  }
}
"""


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class R2ReadsClient:
    def __init__(self, account_tag: str, api_token: str) -> None:
        self._account_tag = account_tag
        self._api_token = api_token

    def fetch_reads(
        self, bucket: str, start: datetime, end: datetime, limit: int = 10000
    ) -> tuple[dict[str, int], bool]:
        response = requests.post(
            CF_GRAPHQL_URL,
            json={
                "query": _QUERY,
                "variables": {
                    "accountTag": self._account_tag,
                    "bucket": bucket,
                    "start": _format_time(start),
                    "end": _format_time(end),
                    "limit": limit,
                },
            },
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("errors"):
            raise CloudflareGraphQLError(str(payload["errors"]))
        accounts = ((payload.get("data") or {}).get("viewer") or {}).get("accounts") or []
        if not accounts:
            raise CloudflareGraphQLError("no account matched CF_ACCOUNT_ID (check token scope)")
        groups = accounts[0]["r2OperationsAdaptiveGroups"]
        reads: dict[str, int] = {}
        for group in groups:
            if group["dimensions"]["actionStatus"] != "success":
                continue
            name = group["dimensions"]["objectName"]
            reads[name] = reads.get(name, 0) + int(group["sum"]["requests"])
        return reads, len(groups) >= limit
