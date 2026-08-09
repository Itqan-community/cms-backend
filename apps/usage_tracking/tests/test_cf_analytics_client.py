from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.usage_tracking.services import cf_analytics_client
from apps.usage_tracking.services.cf_analytics_client import (
    CF_GRAPHQL_URL,
    CloudflareAnalyticsClient,
    CloudflareGraphQLError,
)

_REAL_FIXTURE_PAYLOAD = {
    "data": {
        "viewer": {
            "zones": [
                {
                    "httpRequestsAdaptiveGroups": [
                        {
                            "count": 13,
                            "dimensions": {
                                "cacheStatus": "hit",
                                "clientCountryName": "SA",
                                "clientDeviceType": "desktop",
                                "clientRequestPath": "/media/uploads/assets/2/recitations/001.mp3",
                                "edgeResponseStatus": 304,
                            },
                            "sum": {"edgeResponseBytes": 8809},
                        },
                        {
                            "count": 1,
                            "dimensions": {
                                "cacheStatus": "revalidated",
                                "clientCountryName": "SA",
                                "clientDeviceType": "desktop",
                                "clientRequestPath": "/media/uploads/assets/2/recitations/001.mp3",
                                "edgeResponseStatus": 304,
                            },
                            "sum": {"edgeResponseBytes": 671},
                        },
                        {
                            "count": 1,
                            "dimensions": {
                                "cacheStatus": "miss",
                                "clientCountryName": "SA",
                                "clientDeviceType": "desktop",
                                "clientRequestPath": "/media/uploads/assets/2/recitations/001.mp3",
                                "edgeResponseStatus": 200,
                            },
                            "sum": {"edgeResponseBytes": 869074},
                        },
                        {
                            "count": 1,
                            "dimensions": {
                                "cacheStatus": "hit",
                                "clientCountryName": "SA",
                                "clientDeviceType": "desktop",
                                "clientRequestPath": "/media/uploads/assets/2/recitations/001.mp3",
                                "edgeResponseStatus": 206,
                            },
                            "sum": {"edgeResponseBytes": 1506700},
                        },
                    ]
                }
            ]
        }
    },
    "errors": None,
}


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestCloudflareAnalyticsClient:
    def test_fetch_audio_usage_where_called_should_post_expected_query_variables(self):
        # Arrange
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response({"data": {"viewer": {"zones": []}}, "errors": None})
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1", limit=500)
            start = datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
            end = datetime(2026, 7, 18, 6, 0, tzinfo=UTC)

            # Act
            client.fetch_audio_usage(hostname="cdn.example.com", start=start, end=end)

            # Assert
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == CF_GRAPHQL_URL
            assert kwargs["headers"] == {"Authorization": "Bearer token-1"}
            variables = kwargs["json"]["variables"]
            assert variables == {
                "zoneTag": "zone-1",
                "start": "2026-07-18T00:00:00Z",
                "end": "2026-07-18T06:00:00Z",
                "hostname": "cdn.example.com",
                "pathLike": "%.mp3",
                "source": "eyeball",
                "limit": 500,
            }

    def test_fetch_audio_usage_where_response_has_groups_should_return_parsed_rows(self):
        # Arrange
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response(_REAL_FIXTURE_PAYLOAD)
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1")

            # Act
            result = client.fetch_audio_usage(
                hostname="cdn.example.com",
                start=datetime(2026, 7, 18, 0, 0, tzinfo=UTC),
                end=datetime(2026, 7, 18, 6, 0, tzinfo=UTC),
            )

            # Assert
            assert len(result.rows) == 4
            assert result.rows[0]["dimensions"]["clientRequestPath"] == "/media/uploads/assets/2/recitations/001.mp3"
            assert result.rows[0]["count"] == 13
            assert result.truncated is False

    def test_fetch_audio_usage_where_row_count_hits_limit_should_mark_result_truncated(self):
        # Arrange
        payload = {
            "data": {
                "viewer": {
                    "zones": [
                        {
                            "httpRequestsAdaptiveGroups": [
                                _REAL_FIXTURE_PAYLOAD["data"]["viewer"]["zones"][0]["httpRequestsAdaptiveGroups"][0]
                            ]
                        }
                    ]
                }
            },
            "errors": None,
        }
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response(payload)
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1", limit=1)

            # Act
            result = client.fetch_audio_usage(
                hostname="cdn.example.com",
                start=datetime(2026, 7, 18, 0, 0, tzinfo=UTC),
                end=datetime(2026, 7, 18, 6, 0, tzinfo=UTC),
            )

            # Assert
            assert result.truncated is True

    def test_fetch_audio_usage_where_response_has_no_zones_should_return_empty_result(self):
        # Arrange
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response({"data": {"viewer": {"zones": []}}, "errors": None})
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1")

            # Act
            result = client.fetch_audio_usage(
                hostname="cdn.example.com",
                start=datetime(2026, 7, 18, 0, 0, tzinfo=UTC),
                end=datetime(2026, 7, 18, 6, 0, tzinfo=UTC),
            )

            # Assert
            assert result.rows == []
            assert result.truncated is False

    def test_fetch_audio_usage_where_data_is_none_without_errors_key_should_return_empty_result(self):
        # Arrange
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response({"data": None})
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1")

            # Act
            result = client.fetch_audio_usage(
                hostname="cdn.example.com",
                start=datetime(2026, 7, 18, 0, 0, tzinfo=UTC),
                end=datetime(2026, 7, 18, 6, 0, tzinfo=UTC),
            )

            # Assert
            assert result.rows == []
            assert result.truncated is False

    def test_fetch_audio_usage_where_response_has_graphql_errors_should_raise_cloudflare_graphql_error(self):
        # Arrange
        with patch.object(cf_analytics_client.requests, cf_analytics_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response({"data": None, "errors": [{"message": "quota exceeded"}]})
            client = CloudflareAnalyticsClient(zone_tag="zone-1", api_token="token-1")

            # Act / Assert
            with pytest.raises(CloudflareGraphQLError):
                client.fetch_audio_usage(
                    hostname="cdn.example.com",
                    start=datetime(2026, 7, 18, 0, 0, tzinfo=UTC),
                    end=datetime(2026, 7, 18, 6, 0, tzinfo=UTC),
                )
