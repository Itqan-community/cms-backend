"""End-to-end checks that the @track_usage decorator records the *served* asset's
publisher (not the requester's), across the four tracked public endpoints."""

import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.decorators.track_usage import (
    _RECITER_NAME_CACHE_KEY,
    _resolve_reciter_name,
    _resolve_reciter_names,
)
from apps.users.models import User

_REDIS = "apps.usage_tracking.decorators.track_usage._get_tracking_redis"


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

    def _props(self, mock_get_redis):
        mock_r = mock_get_redis.return_value
        assert mock_r.rpush.called, "expected rpush to be called on Redis mock"
        raw = mock_r.rpush.call_args[0][1]
        return json.loads(raw)["properties"]

    @patch(_REDIS)
    def test_recitations_list_records_distinct_publishers_of_served_assets(self, mock_get_redis):
        response = self.client.get("/recitations/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("recitation", props["entity_type"])
        self.assertCountEqual([self.asset_a.id, self.asset_b.id], props["entity_ids"])
        # Both publishers present -- derived per served asset, not from the requester.
        self.assertCountEqual([self.publisher_a.id, self.publisher_b.id], props["publisher_ids"])

    @patch(_REDIS)
    def test_recitation_detail_records_only_that_assets_publisher(self, mock_get_redis):
        response = self.client.get(f"/recitations/{self.asset_b.id}/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("recitation", props["entity_type"])
        self.assertEqual([self.asset_b.id], props["entity_ids"])
        self.assertEqual(self.asset_b.name, props["accessed_entity_name"])
        # Served asset belongs to publisher_b, NOT the requester's publisher_a.
        self.assertEqual([self.publisher_b.id], props["publisher_ids"])

    @patch(_REDIS)
    def test_recitation_detail_404_dispatches_nothing(self, mock_get_redis):
        response = self.client.get("/recitations/999999/")
        self.assertEqual(404, response.status_code, response.content)
        mock_get_redis.return_value.rpush.assert_not_called()

    @patch(_REDIS)
    def test_reciters_list_records_entities_with_no_publisher(self, mock_get_redis):
        response = self.client.get("/reciters/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("reciter", props["entity_type"])
        self.assertIn(self.reciter.id, props["entity_ids"])
        self.assertEqual([], props["publisher_ids"])

    @patch(_REDIS)
    def test_riwayahs_list_records_entities_with_no_publisher(self, mock_get_redis):
        response = self.client.get("/riwayahs/")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual("riwayah", props["entity_type"])
        self.assertIn(self.riwayah.id, props["entity_ids"])
        self.assertEqual([], props["publisher_ids"])

    @patch(_REDIS)
    def test_reciter_id_filter_records_reciter_name(self, mock_get_redis):
        response = self.client.get(f"/recitations/?reciter_id={self.reciter.id}")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual(self.reciter.id, props["filter_reciter_id"])
        self.assertEqual(self.reciter.name, props["filter_reciter_name"])
        self.assertEqual([self.reciter.name], props["filter_reciter_names"])

    @patch(_REDIS)
    def test_multiple_reciter_id_filters_record_all_names(self, mock_get_redis):
        other_reciter = baker.make("content.Reciter", name="Reciter W", is_active=True)
        baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher_a,
            status=StatusChoice.READY,
            reciter=other_reciter,
            riwayah=self.riwayah,
        )

        response = self.client.get(f"/recitations/?reciter_id={self.reciter.id}&reciter_id={other_reciter.id}")
        self.assertEqual(200, response.status_code, response.content)

        props = self._props(mock_get_redis)
        self.assertEqual([self.reciter.name, other_reciter.name], props["filter_reciter_names"])
        self.assertEqual(self.reciter.name, props["filter_reciter_name"])

    @patch(_REDIS)
    def test_recitations_list_where_qiraah_riwayah_reciter_filters_should_be_sent_to_mixpanel(self, mock_get_redis):
        # Arrange
        qiraah = baker.make("content.Qiraah", name="Qiraah Q", is_active=True)

        # Act
        response = self.client.get(
            f"/recitations/?qiraah_id={qiraah.id}&riwayah_id={self.riwayah.id}&reciter_id={self.reciter.id}"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        props = self._props(mock_get_redis)
        self.assertEqual(qiraah.id, props["filter_qiraah_id"])
        self.assertEqual(self.riwayah.id, props["filter_riwayah_id"])
        self.assertEqual(self.reciter.id, props["filter_reciter_id"])
        # reciter_id additionally resolves a human-readable name for Mixpanel.
        self.assertEqual(self.reciter.name, props["filter_reciter_name"])
        self.assertEqual([self.reciter.name], props["filter_reciter_names"])


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

    def test_batch_resolves_in_order_with_single_query(self):
        other = baker.make("content.Reciter", name="Reciter Q")
        with self.assertNumQueries(1):
            names = _resolve_reciter_names([self.reciter.id, other.id])
        self.assertEqual(["Reciter Z", "Reciter Q"], names)
        # Both are now cached -- a repeat resolve hits no query.
        with self.assertNumQueries(0):
            self.assertEqual(["Reciter Z", "Reciter Q"], _resolve_reciter_names([self.reciter.id, other.id]))

    def test_batch_resolves_only_uncached_misses(self):
        other = baker.make("content.Reciter", name="Reciter Q")
        _resolve_reciter_names([self.reciter.id])  # warm the cache for one id
        # Only the uncached id triggers a query; cached one is reused.
        with self.assertNumQueries(1):
            names = _resolve_reciter_names([self.reciter.id, other.id])
        self.assertEqual(["Reciter Z", "Reciter Q"], names)

    def test_batch_missing_reciter_resolves_to_none(self):
        names = _resolve_reciter_names([self.reciter.id, 999999])
        self.assertEqual(["Reciter Z", None], names)

    def test_resolve_where_arabic_name_exists_should_prefer_arabic(self):
        # Arrange
        reciter = baker.make("content.Reciter", name_en="Mishary", name_ar="مشاري")

        # Act
        names = _resolve_reciter_names([reciter.id])

        # Assert
        self.assertEqual(["مشاري"], names)

    def test_resolve_where_arabic_name_missing_should_fall_back_to_english(self):
        # Arrange
        reciter = baker.make("content.Reciter", name_en="Mishary", name_ar="")

        # Act
        names = _resolve_reciter_names([reciter.id])

        # Assert
        self.assertEqual(["Mishary"], names)
