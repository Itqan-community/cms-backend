from unittest.mock import MagicMock, patch

import pytest
import responses

from apps.usage_tracking.services.mixpanel_client import (
    MixpanelIngestClient,
    MixpanelQueryError,
    MixpanelSegmentationClient,
)


class TestMixpanelIngestClient:
    @patch("apps.usage_tracking.services.mixpanel_client.Mixpanel")
    def test_track_valid_payload_calls_sdk(self, mock_mixpanel_cls):
        sdk_instance = MagicMock()
        mock_mixpanel_cls.return_value = sdk_instance

        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)
        client.track(distinct_id="anon-1", event="public_api_request", properties={"endpoint": "GET /reciters"})

        sdk_instance.track.assert_called_once_with("anon-1", "public_api_request", {"endpoint": "GET /reciters"})

    @patch("apps.usage_tracking.services.mixpanel_client.Mixpanel")
    def test_track_feature_flag_off_noop(self, mock_mixpanel_cls):
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=False)

        client.track(distinct_id="anon-1", event="public_api_request", properties={})

        mock_mixpanel_cls.assert_not_called()

    @patch("apps.usage_tracking.services.mixpanel_client.Mixpanel")
    def test_track_no_token_noop(self, mock_mixpanel_cls):
        client = MixpanelIngestClient(token="", ingest_host="api-eu.mixpanel.com", enabled=True)

        client.track(distinct_id="anon-1", event="public_api_request", properties={})

        mock_mixpanel_cls.assert_not_called()


class TestMixpanelSegmentationClient:
    BASE = "https://eu.mixpanel.com"

    def _client(self):
        return MixpanelSegmentationClient(
            api_base=self.BASE,
            project_id="4012890",
            service_username="svc-user",
            service_secret="svc-secret",
        )

    @responses.activate
    def test_query_builds_correct_url_and_auth(self):
        responses.add(
            responses.GET,
            f"{self.BASE}/api/2.0/segmentation",
            json={"data": {"series": ["2026-04-13"], "values": {}}},
            status=200,
        )

        result = self._client().query(
            event="public_api_request",
            from_date="2026-04-01",
            to_date="2026-04-13",
        )

        assert result["data"]["series"] == ["2026-04-13"]
        call = responses.calls[0]
        assert "Authorization" in call.request.headers
        assert call.request.headers["Authorization"].startswith("Basic ")
        dict(call.request.params if hasattr(call.request, "params") else {})
        # query string parsing
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(call.request.url).query)
        assert qs["event"] == ["public_api_request"]
        assert qs["from_date"] == ["2026-04-01"]
        assert qs["to_date"] == ["2026-04-13"]
        assert qs["project_id"] == ["4012890"]

    @responses.activate
    def test_query_passes_where_clause(self):
        responses.add(
            responses.GET,
            f"{self.BASE}/api/2.0/segmentation",
            json={"data": {}},
            status=200,
        )

        self._client().query(
            event="public_api_request",
            from_date="2026-04-01",
            to_date="2026-04-13",
            where='properties["publisher_id"] == 42',
        )

        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(responses.calls[0].request.url).query)
        assert qs["where"] == ['properties["publisher_id"] == 42']

    @responses.activate
    def test_query_with_breakdown_passes_on_param(self):
        responses.add(
            responses.GET,
            f"{self.BASE}/api/2.0/segmentation",
            json={"data": {}},
            status=200,
        )

        self._client().query(
            event="public_api_request",
            from_date="2026-04-01",
            to_date="2026-04-13",
            on='properties["endpoint"]',
        )

        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(responses.calls[0].request.url).query)
        assert qs["on"] == ['properties["endpoint"]']

    @responses.activate
    def test_query_non_ok_raises_error(self):
        responses.add(
            responses.GET,
            f"{self.BASE}/api/2.0/segmentation",
            json={"error": "bad request"},
            status=400,
        )

        with pytest.raises(MixpanelQueryError):
            self._client().query(
                event="public_api_request",
                from_date="2026-04-01",
                to_date="2026-04-13",
            )
