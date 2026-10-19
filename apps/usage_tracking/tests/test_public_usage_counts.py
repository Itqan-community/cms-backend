from datetime import date

from django.core.cache import cache
from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import TrafficDaily
from apps.usage_tracking.services.usage_reports import round_public


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": "audio_surah", "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


@override_settings(PUBLIC_USAGE_COUNTS_ENABLED=True)
class TestPublicUsageCounts(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.asset = baker.make(Asset, publisher=baker.make(Publisher), name="Mushaf", category=CategoryChoice.MUSHAF)
        daily(date(2025, 1, 3), asset_id=self.asset.id, sessions=1234, app_id=1, channel="app_identified")
        daily(date(2026, 10, 3), asset_id=self.asset.id, kind="version_file", sessions=40, app_id=2)
        daily(date(2026, 10, 3), asset_id=self.asset.id, kind="cli_install", sessions=7)
        daily(date(2026, 10, 3), asset_id=self.asset.id, kind="view", sessions=99, app_id=3)

    def test_usage_counts_where_enabled_should_return_rounded_all_time_counts(self):
        # Act
        response = self.client.get(f"/cms-api/assets/{self.asset.id}/usage-counts/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert (body["plays"], body["downloads"], body["apps"]) == (1200, 47, 2)
        assert [item["code"] for item in body["disclaimers"]][0] == "lower_bound"

    @override_settings(PUBLIC_USAGE_COUNTS_ENABLED=False)
    def test_usage_counts_where_disabled_should_return_404(self):
        # Act
        response = self.client.get(f"/cms-api/assets/{self.asset.id}/usage-counts/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("usage_counts_disabled", response.json()["error_name"])

    def test_usage_counts_where_asset_restricted_for_tenant_should_return_404(self):
        # Arrange
        Asset.objects.filter(id=self.asset.id).update(restricted_for_tenant=True)

        # Act
        response = self.client.get(f"/cms-api/assets/{self.asset.id}/usage-counts/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_usage_counts_where_called_twice_should_serve_counts_from_cache(self):
        # Arrange
        self.client.get(f"/cms-api/assets/{self.asset.id}/usage-counts/")

        # Act
        with self.assertNumQueries(1):  # the asset visibility check only
            response = self.client.get(f"/cms-api/assets/{self.asset.id}/usage-counts/")

        # Assert
        assert response.json()["plays"] == 1200

    def test_round_public_where_values_vary_should_floor_to_two_significant_figures(self):
        # Act / Assert
        assert [round_public(value) for value in (0, 7, 87, 999, 1234, 98765)] == [0, 7, 87, 990, 1200, 98000]
