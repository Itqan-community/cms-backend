from unittest.mock import MagicMock, patch

from apps.usage_tracking.tasks import track_api_request_task


class TestTrackApiRequestTask:
    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_sends_to_client(self, mock_build):
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
    def test_task_passes_accessed_entity_name_from_properties_without_db(self, mock_build):
        """Regression: entity name must come from properties, never from a DB query."""
        client = MagicMock()
        mock_build.return_value = client

        track_api_request_task.run(
            distinct_id="app-7",
            event="public_api_request",
            properties={
                "accessed_entity_id": 99,
                "accessed_entity_name": "Ibn Kathir",
                "entity_type": "recitation",
            },
        )

        sent_props = client.track.call_args[0][2]
        assert sent_props["accessed_entity_name"] == "Ibn Kathir"

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_does_not_touch_db_for_entity_name(self, mock_build):
        """Celery task must make zero DB queries - connection exhaustion fix."""
        client = MagicMock()
        mock_build.return_value = client

        with patch("apps.content.models.Asset") as mock_asset:
            track_api_request_task.run(
                distinct_id="app-7",
                event="public_api_request",
                properties={"accessed_entity_id": 99},
            )
            mock_asset.objects.filter.assert_not_called()
