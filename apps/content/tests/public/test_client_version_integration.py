"""End-to-end checks that a public API consumer's self-reported client name and version
travel from the request headers through the middleware to the usage-tracking payload."""

import json
from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.middlewares.client_version import WARNING_HEADER
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.decorators import track_usage as track_usage_module
from apps.usage_tracking.decorators.track_usage import _get_tracking_redis

_REDIS = f"{track_usage_module.__name__}.{_get_tracking_redis.__name__}"


class ClientVersionIntegrationTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher A")
        self.reciter = baker.make("content.Reciter", name="Reciter X", is_active=True)
        self.riwayah = baker.make("content.Riwayah", name="Riwayah Y", is_active=True)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            reciter=self.reciter,
            riwayah=self.riwayah,
        )

    def _props(self, mock_get_redis):
        mock_r = mock_get_redis.return_value
        assert mock_r.rpush.called, "expected rpush to be called on Redis mock"
        return json.loads(mock_r.rpush.call_args[0][1])["properties"]

    @patch(_REDIS)
    def test_recitations_list_where_client_headers_sent_should_track_name_and_version(self, mock_get_redis):
        # Arrange
        headers = {"X-Client-Name": "quran-companion", "X-Client-Version": "2.4.1"}

        # Act
        response = self.client.get("/recitations/", headers=headers)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn(WARNING_HEADER, response)
        props = self._props(mock_get_redis)
        self.assertEqual("quran-companion", props["client_name"])
        self.assertEqual("2.4.1", props["client_version"])

    @patch(_REDIS)
    def test_recitations_list_where_no_client_headers_sent_should_track_nulls(self, mock_get_redis):
        # Arrange / Act
        response = self.client.get("/recitations/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn(WARNING_HEADER, response)
        props = self._props(mock_get_redis)
        self.assertIsNone(props["client_name"])
        self.assertIsNone(props["client_version"])

    @patch(_REDIS)
    def test_recitations_list_where_client_version_is_malformed_should_succeed_and_warn(self, mock_get_redis):
        # Arrange
        headers = {"X-Client-Name": "quran-companion", "X-Client-Version": "2.4.1 (nightly build)"}

        # Act
        response = self.client.get("/recitations/", headers=headers)

        # Assert -- the request still succeeds; only the bad value is dropped.
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("X-Client-Version", response[WARNING_HEADER])
        props = self._props(mock_get_redis)
        self.assertEqual("quran-companion", props["client_name"])
        self.assertIsNone(props["client_version"])

    def test_error_response_where_client_headers_sent_should_still_carry_the_warning(self):
        # Arrange -- a 404 short-circuits the tracked view entirely.
        headers = {"X-Client-Version": "not a version"}

        # Act
        response = self.client.get("/recitations/999999/", headers=headers)

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertIn("X-Client-Version", response[WARNING_HEADER])
