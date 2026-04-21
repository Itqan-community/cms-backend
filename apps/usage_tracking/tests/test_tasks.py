from unittest.mock import MagicMock, patch

from apps.usage_tracking.tasks import track_api_request_task


class TestTrackApiRequestTask:
    @patch("apps.usage_tracking.tasks._build_ingest_clients")
    def test_task_fans_out_to_all_clients(self, mock_build):
        client_a = MagicMock()
        client_b = MagicMock()
        mock_build.return_value = [client_a, client_b]

        track_api_request_task.run(
            distinct_id="anon-1",
            event="public_api_request",
            properties={"endpoint": "GET /reciters", "status_code": 200},
        )

        for client in [client_a, client_b]:
            client.track.assert_called_once_with(
                "anon-1",
                "public_api_request",
                {"endpoint": "GET /reciters", "status_code": 200},
            )

    @patch("apps.usage_tracking.tasks._build_ingest_clients")
    def test_task_swallows_empty_distinct_id(self, mock_build):
        client = MagicMock()
        mock_build.return_value = [client]

        track_api_request_task.run(distinct_id="", event="public_api_request", properties={})

        client.track.assert_not_called()

    @patch("apps.usage_tracking.tasks._build_ingest_clients")
    def test_task_fans_out_to_single_client_when_only_one_token(self, mock_build):
        client = MagicMock()
        mock_build.return_value = [client]

        track_api_request_task.run(
            distinct_id="user-1",
            event="public_api_request",
            properties={},
        )

        client.track.assert_called_once()
