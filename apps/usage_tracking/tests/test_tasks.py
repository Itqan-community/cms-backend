from unittest.mock import MagicMock, patch

import pytest

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.tasks import UnexpectedDatabaseQuery, no_db_queries, track_api_request_task


class TestTrackApiRequestTask(BaseTestCase):
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
    def test_task_forwards_pre_resolved_entity_name(self, mock_build):
        """The entity name is resolved at the call site and passed through verbatim."""
        client = MagicMock()
        mock_build.return_value = client

        track_api_request_task.run(
            distinct_id="user-1",
            event="public_api_request",
            properties={"accessed_entity_name": "Hafs An Asim", "entity_type": "recitation"},
        )

        sent_props = client.track.call_args[0][2]
        assert sent_props["accessed_entity_name"] == "Hafs An Asim"

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_runs_without_db_queries(self, mock_build):
        """The task body resolves nothing from the database; everything it needs is
        passed in via ``properties``."""
        client = MagicMock()
        mock_build.return_value = client

        with self.assertNumQueries(0):
            track_api_request_task.run(
                distinct_id="user-1",
                event="public_api_request",
                properties={"accessed_entity_name": "Hafs An Asim", "entity_type": "recitation"},
            )

        sent_props = client.track.call_args[0][2]
        assert sent_props["accessed_entity_name"] == "Hafs An Asim"

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    def test_task_raises_if_body_issues_a_query(self, mock_build):
        """The no_db_queries guard turns any stray query inside the task into a hard error,
        so a future regression that re-adds a DB lookup fails loudly instead of silently."""
        from apps.content.models import Asset

        client = MagicMock()
        client.track.side_effect = lambda *a, **kw: Asset.objects.filter(pk=1).exists()
        mock_build.return_value = client

        with pytest.raises(UnexpectedDatabaseQuery):
            track_api_request_task.run(
                distinct_id="user-1",
                event="public_api_request",
                properties={"entity_type": "recitation"},
            )


class TestNoDbQueries(BaseTestCase):

    def test_allows_block_without_queries(self):
        with no_db_queries():
            pass  # no query, no error

    def test_raises_on_query(self):
        from apps.content.models import Asset

        with pytest.raises(UnexpectedDatabaseQuery), no_db_queries():
            Asset.objects.filter(pk=1).exists()
