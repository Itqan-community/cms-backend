from unittest.mock import MagicMock, patch

from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient


class TestMixpanelIngestClient:
    @patch("apps.usage_tracking.services.mixpanel_client.Mixpanel")
    def test_track_valid_payload_calls_sdk(self, mock_mixpanel_cls):
        sdk_instance = MagicMock()
        mock_mixpanel_cls.return_value = sdk_instance

        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)
        client.track(distinct_id="anon-1", event="public_api_request", properties={"endpoint": "GET /reciters"})

        sdk_instance.track.assert_called_once_with(
            "anon-1", "public_api_request", {"endpoint": "GET /reciters"}, meta=None
        )

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
