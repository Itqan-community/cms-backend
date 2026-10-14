from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.usage_tracking.services import cf_downloads_client
from apps.usage_tracking.services.cf_analytics_client import CloudflareGraphQLError
from apps.usage_tracking.services.cf_downloads_client import CloudflareDownloadsClient, DatasetLimits

_START = datetime(2026, 10, 13, 10, tzinfo=UTC)
_END = datetime(2026, 10, 13, 11, tzinfo=UTC)

# Shapes recorded from production on 2026-10-13 (IPs replaced).
_EVENT = {
    "clientCountryName": "SA",
    "clientIP": "203.0.113.7",
    "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
    "datetime": "2026-10-13T10:00:18Z",
    "edgeResponseStatus": 200,
    "rayName": "a49d7f1abc4ee1e0",
}
_TOTAL = {
    "count": 4,
    "avg": {"sampleInterval": 1},
    "sum": {"edgeResponseBytes": 29797257},
    "dimensions": {
        "clientCountryName": "SA",
        "clientRequestPath": "/media/uploads/assets/14/recitations/035.mp3",
        "edgeResponseStatus": 206,
    },
}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _zone_payload(**zone: object) -> dict:
    return {"data": {"viewer": {"zones": [zone]}}}


def _patch_post(payload: dict):
    return patch.object(
        cf_downloads_client.requests, cf_downloads_client.requests.post.__name__, return_value=_response(payload)
    )


class TestCloudflareDownloadsClient:
    def setup_method(self):
        self.client = CloudflareDownloadsClient(zone_tag="zone-1", api_token="token-1", hostname="cdn.example.com")

    def test_fetch_events_where_ok_should_send_filters_and_return_rows(self):
        # Arrange
        with _patch_post(_zone_payload(httpRequestsAdaptive=[_EVENT])) as post:
            # Act
            rows = self.client.fetch_events(_START, _END, limit=10000)

        # Assert
        assert rows == [_EVENT]
        body = post.call_args.kwargs["json"]
        assert body["variables"] == {
            "zoneTag": "zone-1",
            "start": "2026-10-13T10:00:00Z",
            "end": "2026-10-13T11:00:00Z",
            "hostname": "cdn.example.com",
            "pathLike": "/media/uploads/assets/%",
            "limit": 10000,
        }
        assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer token-1"}

    def test_fetch_totals_where_ok_should_return_rows(self):
        # Arrange
        with _patch_post(_zone_payload(httpRequestsAdaptiveGroups=[_TOTAL])):
            # Act
            rows = self.client.fetch_totals(_START, _END, limit=10000)

        # Assert
        assert rows == [_TOTAL]

    def test_fetch_limits_where_ok_should_parse_settings(self):
        # Arrange
        payload = _zone_payload(settings={"httpRequestsAdaptive": {"maxPageSize": 10000, "notOlderThan": 2678400}})
        with _patch_post(payload):
            # Act
            limits = self.client.fetch_limits()

        # Assert
        assert limits == DatasetLimits(max_page_size=10000, not_older_than=timedelta(days=31))

    def test_fetch_events_where_graphql_errors_should_raise(self):
        # Arrange
        payload = {"data": None, "errors": [{"message": 'unknown field "x"'}]}
        with _patch_post(payload), pytest.raises(CloudflareGraphQLError):
            # Act
            self.client.fetch_events(_START, _END, limit=10000)

    def test_fetch_events_where_zone_not_matched_should_raise(self):
        # Arrange
        payload = {"data": {"viewer": {"zones": []}}}
        with _patch_post(payload), pytest.raises(CloudflareGraphQLError):
            # Act
            self.client.fetch_events(_START, _END, limit=10000)
