from unittest.mock import MagicMock

from apps.usage_tracking.services import usage_queries


class TestUsageQueries:
    def _mock_client(self):
        client = MagicMock()
        client.query.return_value = {"data": {}}
        return client

    def test_timeseries_passes_publisher_where(self):
        client = self._mock_client()

        usage_queries.get_timeseries("2026-04-01", "2026-04-13", publisher_id=42, client=client)

        _, kwargs = client.query.call_args
        assert kwargs["event"] == "public_api_request"
        assert kwargs["where"] == 'properties["publisher_id"] == 42'

    def test_timeseries_without_publisher_omits_where(self):
        client = self._mock_client()

        usage_queries.get_timeseries("2026-04-01", "2026-04-13", publisher_id=None, client=client)

        _, kwargs = client.query.call_args
        assert kwargs["where"] is None

    def test_top_endpoints_breaks_down_on_endpoint(self):
        client = self._mock_client()

        usage_queries.get_top_endpoints("2026-04-01", "2026-04-13", publisher_id=42, client=client)

        _, kwargs = client.query.call_args
        assert kwargs["on"] == 'properties["endpoint"]'
        assert kwargs["where"] == 'properties["publisher_id"] == 42'

    def test_top_entities_breaks_down_on_entity_ids(self):
        client = self._mock_client()

        usage_queries.get_top_entities("2026-04-01", "2026-04-13", publisher_id=7, client=client)

        _, kwargs = client.query.call_args
        assert kwargs["on"] == 'properties["entity_ids"]'
        assert kwargs["where"] == 'properties["publisher_id"] == 7'
