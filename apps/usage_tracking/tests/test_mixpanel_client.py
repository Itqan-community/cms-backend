from unittest.mock import MagicMock, patch

import pytest
import requests

from apps.usage_tracking.services import mixpanel_client
from apps.usage_tracking.services.mixpanel_client import _IMPORT_CHUNK_SIZE, MixpanelIngestClient


def _mock_response(status_code: int = 200, num_records_imported: int = 0) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {
        "status": "OK" if status_code < 400 else "FAIL",
        "num_records_imported": num_records_imported,
    }
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code} error")
    else:
        response.raise_for_status.return_value = None
    return response


def _make_import_event(index: int = 0) -> dict:
    return {"event": "audio_usage_summary", "properties": {"time": 0, "distinct_id": "", "$insert_id": str(index)}}


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


class TestImportEvents:
    def test_import_events_where_disabled_should_be_noop(self):
        # Arrange
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=False)

        # Act / Assert
        with patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post:
            assert client.import_events([_make_import_event()]) == 0
            mock_post.assert_not_called()

    def test_import_events_where_no_token_should_be_noop(self):
        # Arrange
        client = MixpanelIngestClient(token="", ingest_host="api-eu.mixpanel.com", enabled=True)

        # Act / Assert
        with patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post:
            assert client.import_events([_make_import_event()]) == 0
            mock_post.assert_not_called()

    def test_import_events_where_events_empty_should_be_noop(self):
        # Arrange
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)

        # Act / Assert
        with patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post:
            assert client.import_events([]) == 0
            mock_post.assert_not_called()

    def test_import_events_where_events_exceed_chunk_size_should_send_two_posts(self):
        # Arrange
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)
        events = [_make_import_event(i) for i in range(_IMPORT_CHUNK_SIZE + 1)]

        with patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post:
            mock_post.return_value = _mock_response(num_records_imported=1)

            # Act
            client.import_events(events)

            # Assert
            assert mock_post.call_count == 2
            first_chunk = mock_post.call_args_list[0].kwargs["json"]
            second_chunk = mock_post.call_args_list[1].kwargs["json"]
            assert len(first_chunk) == _IMPORT_CHUNK_SIZE
            assert len(second_chunk) == 1

    def test_import_events_where_posts_succeed_should_sum_num_records_imported(self):
        # Arrange
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)
        events = [_make_import_event(i) for i in range(_IMPORT_CHUNK_SIZE + 1)]

        with patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post:
            mock_post.side_effect = [
                _mock_response(num_records_imported=_IMPORT_CHUNK_SIZE),
                _mock_response(num_records_imported=1),
            ]

            # Act
            total = client.import_events(events)

            # Assert
            assert total == _IMPORT_CHUNK_SIZE + 1

    def test_import_events_where_response_is_400_should_log_then_raise(self):
        # Arrange
        client = MixpanelIngestClient(token="test-token", ingest_host="api-eu.mixpanel.com", enabled=True)

        with (
            patch.object(mixpanel_client.requests, mixpanel_client.requests.post.__name__) as mock_post,
            patch.object(mixpanel_client, "logger") as mock_logger,
        ):
            mock_post.return_value = _mock_response(status_code=400)

            # Act / Assert
            with pytest.raises(requests.HTTPError):
                client.import_events([_make_import_event()])
            error_messages = [call.args[0] for call in mock_logger.error.call_args_list]
            assert any("/import returned %d" in message for message in error_messages)
