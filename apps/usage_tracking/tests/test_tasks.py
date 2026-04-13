from unittest.mock import patch

from apps.usage_tracking.tasks import track_api_request_task


class TestTrackApiRequestTask:
    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_calls_ingest_client_with_event(self, mock_build):
        client = mock_build.return_value

        track_api_request_task.run(
            distinct_id="anon-1",
            event="public_api_request",
            properties={"endpoint": "GET /reciters", "status_code": 200},
        )

        client.track.assert_called_once_with(
            "anon-1",
            "public_api_request",
            {"endpoint": "GET /reciters", "status_code": 200},
        )

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_swallows_empty_distinct_id(self, mock_build):
        client = mock_build.return_value

        track_api_request_task.run(distinct_id="", event="public_api_request", properties={})

        client.track.assert_not_called()
