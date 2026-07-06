import json
from unittest.mock import MagicMock, patch

import pytest
import redis

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.tasks import (
    _TRACKING_INFLIGHT_KEY,
    TRACKING_BUFFER_KEY,
    UnexpectedDatabaseQuery,
    flush_tracking_buffer_task,
    no_db_queries,
    track_api_request_task,
)


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


def _make_event(distinct_id="user-1", event="public_api_request", props=None):
    return {
        "distinct_id": distinct_id,
        "event": event,
        "properties": props or {"endpoint": "GET /recitations/"},
        "meta": {},
    }


class TestFlushTrackingBufferTask:
    def _mock_redis_with_events(self, events):
        """Return a mock Redis client that simulates a buffer containing the given events."""
        mock_r = MagicMock()
        mock_r.rename.return_value = True
        mock_r.lrange.return_value = [json.dumps(e) for e in events]
        return mock_r

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    @patch("apps.usage_tracking.tasks._get_tracking_redis")
    def test_flush_tracking_buffer_task_where_buffer_has_events_should_send_batch(self, mock_get_redis, mock_build):
        events = [_make_event("user-1"), _make_event("user-2")]
        mock_r = self._mock_redis_with_events(events)
        mock_get_redis.return_value = mock_r
        client = MagicMock()
        mock_build.return_value = client

        flush_tracking_buffer_task.run()

        mock_r.rename.assert_called_once_with(TRACKING_BUFFER_KEY, _TRACKING_INFLIGHT_KEY)
        mock_r.lrange.assert_called_once_with(_TRACKING_INFLIGHT_KEY, 0, -1)
        mock_r.delete.assert_called_once_with(_TRACKING_INFLIGHT_KEY)
        client.track_batch.assert_called_once()
        sent = client.track_batch.call_args[0][0]
        assert len(sent) == 2
        assert sent[0]["distinct_id"] == "user-1"
        assert sent[1]["distinct_id"] == "user-2"

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    @patch("apps.usage_tracking.tasks._get_tracking_redis")
    def test_flush_tracking_buffer_task_where_buffer_empty_should_be_noop(self, mock_get_redis, mock_build):
        mock_r = MagicMock()
        mock_r.rename.side_effect = redis.ResponseError("ERR no such key")
        mock_get_redis.return_value = mock_r
        client = MagicMock()
        mock_build.return_value = client

        flush_tracking_buffer_task.run()

        mock_r.lrange.assert_not_called()
        client.track_batch.assert_not_called()

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    @patch("apps.usage_tracking.tasks._get_tracking_redis")
    def test_flush_tracking_buffer_task_where_inflight_is_empty_after_rename_should_be_noop(
        self, mock_get_redis, mock_build
    ):
        mock_r = MagicMock()
        mock_r.rename.return_value = True
        mock_r.lrange.return_value = []
        mock_get_redis.return_value = mock_r
        client = MagicMock()
        mock_build.return_value = client

        flush_tracking_buffer_task.run()

        client.track_batch.assert_not_called()

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    @patch("apps.usage_tracking.tasks._get_tracking_redis")
    def test_flush_tracking_buffer_task_where_track_batch_raises_should_still_delete_inflight(
        self, mock_get_redis, mock_build
    ):
        """Inflight key is always deleted after the send attempt.

        A network failure drops the batch (analytics loss is acceptable) but must
        not leave the inflight key lingering -- next RENAME would silently overwrite
        it, losing both old and new data.
        """
        events = [_make_event("user-1")]
        mock_r = self._mock_redis_with_events(events)
        mock_get_redis.return_value = mock_r
        client = MagicMock()
        client.track_batch.side_effect = ConnectionError("Mixpanel down")
        mock_build.return_value = client

        with pytest.raises(ConnectionError):
            flush_tracking_buffer_task.run()

        mock_r.delete.assert_called_once_with(_TRACKING_INFLIGHT_KEY)

    @patch("apps.usage_tracking.tasks._build_ingest_client")
    @patch("apps.usage_tracking.tasks._get_tracking_redis")
    def test_flush_tracking_buffer_task_where_event_is_malformed_json_should_skip_it(self, mock_get_redis, mock_build):
        mock_r = MagicMock()
        mock_r.rename.return_value = True
        mock_r.lrange.return_value = ["not-json", json.dumps(_make_event("user-good"))]
        mock_get_redis.return_value = mock_r
        client = MagicMock()
        mock_build.return_value = client

        flush_tracking_buffer_task.run()

        sent = client.track_batch.call_args[0][0]
        assert len(sent) == 1
        assert sent[0]["distinct_id"] == "user-good"
