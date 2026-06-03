from unittest.mock import MagicMock, patch

from apps.usage_tracking.tasks import track_api_request_task


class TestTrackApiRequestTask:
    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_fans_out_to_all_clients(self, mock_build):
        client = MagicMock()
        mock_build.return_value = client

        track_api_request_task.run(
            distinct_id="anon-1",
            event="public_api_request",
            properties={"endpoint": "GET /reciters", "status_code": 200},
        )

        client.track.assert_called_once_with(
            "anon-1", "public_api_request", {"endpoint": "GET /reciters", "status_code": 200}, meta=None
        )

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_swallows_empty_distinct_id(self, mock_build):
        client = MagicMock()
        mock_build.return_value = client

        track_api_request_task.run(distinct_id="", event="public_api_request", properties={})

        client.track.assert_not_called()

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_fans_out_to_single_client_when_only_one_token(self, mock_build):
        client = MagicMock()
        mock_build.return_value = client

        track_api_request_task.run(
            distinct_id="user-1",
            event="public_api_request",
            properties={},
        )

        client.track.assert_called_once()

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_resolves_accessed_entity_name(self, mock_build):
        client = MagicMock()
        mock_build.return_value = client

        with patch("apps.content.models.Asset.objects") as mock_qs:
            mock_qs.filter.return_value.values.return_value.first.return_value = {"name": "Hafs An Asim"}

            track_api_request_task.run(
                distinct_id="user-1",
                event="public_api_request",
                properties={"accessed_entity_id": 99, "entity_type": "recitation"},
            )

        sent_props = client.track.call_args[0][2]
        assert sent_props["accessed_entity_name"] == "Hafs An Asim"

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_accessed_entity_name_none_when_not_found(self, mock_build):
        client = MagicMock()
        mock_build.return_value = client

        with patch("apps.content.models.Asset.objects") as mock_qs:
            mock_qs.filter.return_value.values.return_value.first.return_value = None

            track_api_request_task.run(
                distinct_id="user-1",
                event="public_api_request",
                properties={"accessed_entity_id": 99},
            )

        sent_props = client.track.call_args[0][2]
        assert sent_props["accessed_entity_name"] is None
