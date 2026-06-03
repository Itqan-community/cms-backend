"""End-to-end checks that the @track_usage decorator records the *served* asset's
publisher (not the requester's), across the four tracked public endpoints."""

from unittest.mock import patch

from django.core.cache import cache
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.decorators.track_usage import _RECITER_NAME_CACHE_KEY, _resolve_reciter_name
from apps.users.models import User

_TASK = "apps.usage_tracking.decorators.track_usage.track_api_request_task"


class UsageTrackingIntegrationTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Two distinct publishers so we can prove publisher comes from the asset.
        self.publisher_a = baker.make(Publisher, name="Publisher A")
        self.publisher_b = baker.make(Publisher, name="Publisher B")
        self.reciter = baker.make("content.Reciter", name="Reciter X", is_active=True)
        self.riwayah = baker.make("content.Riwayah", name="Riwayah Y", is_active=True)

        self.asset_a = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher_a,
            status=StatusChoice.READY,
            reciter=self.reciter,
            riwayah=self.riwayah,
        )
        self.asset_b = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher_b,
            status=StatusChoice.READY,
            reciter=self.reciter,
            riwayah=self.riwayah,
        )

        # The requesting app's owner belongs to publisher_a -- the old resolver would
        # have wrongly attributed every served asset to publisher_a.
        self.user = User.objects.create_user(email="oauth@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        self.authenticate_client(self.app)

    def _props(self, mock_task):
        assert mock_task.delay.called
        return mock_task.delay.call_args.kwargs["properties"]

    @patch(_TASK)
    def test_recitations_list_records_distinct_publishers_of_served_assets(self, mock_task):
        response = self.client.get("/recitations/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_task)
        self.assertEqual("recitation", props["entity_type"])
        self.assertCountEqual([self.asset_a.id, self.asset_b.id], props["entity_ids"])
        # Both publishers present -- derived per served asset, not from the requester.
        self.assertCountEqual([self.publisher_a.id, self.publisher_b.id], props["publisher_ids"])

    @patch(_TASK)
    def test_recitation_detail_records_only_that_assets_publisher(self, mock_task):
        response = self.client.get(f"/recitations/{self.asset_b.id}/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_task)
        self.assertEqual("recitation", props["entity_type"])
        self.assertEqual([self.asset_b.id], props["entity_ids"])
        self.assertEqual(self.asset_b.id, props["accessed_entity_id"])
        # Served asset belongs to publisher_b, NOT the requester's publisher_a.
        self.assertEqual([self.publisher_b.id], props["publisher_ids"])

    @patch(_TASK)
    def test_recitation_detail_404_dispatches_nothing(self, mock_task):
        response = self.client.get("/recitations/999999/")
        self.assertEqual(404, response.status_code, response.content)
        mock_task.delay.assert_not_called()

    @patch(_TASK)
    def test_reciters_list_records_entities_with_no_publisher(self, mock_task):
        response = self.client.get("/reciters/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_task)
        self.assertEqual("reciter", props["entity_type"])
        self.assertIn(self.reciter.id, props["entity_ids"])
        self.assertEqual([], props["publisher_ids"])

    @patch(_TASK)
    def test_riwayahs_list_records_entities_with_no_publisher(self, mock_task):
        response = self.client.get("/riwayahs/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_task)
        self.assertEqual("riwayah", props["entity_type"])
        self.assertIn(self.riwayah.id, props["entity_ids"])
        self.assertEqual([], props["publisher_ids"])

    @patch(_TASK)
    def test_reciter_id_filter_records_reciter_name(self, mock_task):
        response = self.client.get(f"/recitations/?reciter_id={self.reciter.id}")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_task)
        self.assertEqual(self.reciter.id, props["filter_reciter_id"])
        self.assertEqual(self.reciter.name, props["filter_reciter_name"])


class ResolveReciterNameTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.reciter = baker.make("content.Reciter", name="Reciter Z")

    def test_resolves_and_caches_name(self):
        with self.assertNumQueries(1):
            self.assertEqual("Reciter Z", _resolve_reciter_name(self.reciter.id))
        # Second call is served from cache -- no query.
        with self.assertNumQueries(0):
            self.assertEqual("Reciter Z", _resolve_reciter_name(self.reciter.id))
        self.assertEqual("Reciter Z", cache.get(_RECITER_NAME_CACHE_KEY.format(id=self.reciter.id)))

    def test_missing_reciter_returns_none_and_caches_empty(self):
        with self.assertNumQueries(1):
            self.assertIsNone(_resolve_reciter_name(999999))
        with self.assertNumQueries(0):
            self.assertIsNone(_resolve_reciter_name(999999))
