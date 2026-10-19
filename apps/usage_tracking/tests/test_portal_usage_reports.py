from datetime import date

from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.usage_tracking.models import TrafficDaily
from apps.users.models import User

BASE = "/portal/usage"
RANGE = "start_date=2026-10-10&end_date=2026-10-16"


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": "audio_surah", "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


class TestPortalUsageReports(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(email="member@example.com", name="Member")
        self.publisher = baker.make(Publisher, name="Pub A")
        self.other_publisher = baker.make(Publisher, name="Pub B")
        baker.make(
            PublisherMember, user=self.user, publisher=self.publisher, status=PublisherMember.StatusChoice.ACTIVE
        )
        self.asset = baker.make(Asset, publisher=self.publisher, name="Asset A", category=CategoryChoice.MUSHAF)
        self.other_asset = baker.make(
            Asset, publisher=self.other_publisher, name="Asset B", category=CategoryChoice.MUSHAF
        )
        daily(date(2026, 10, 12), asset_id=self.asset.id, sessions=5, requests=6, bytes=10)
        daily(date(2026, 10, 12), asset_id=self.other_asset.id, sessions=100, requests=100, country="EG")
        daily(date(2026, 10, 12), kind="api_call", sessions=50, requests=50)  # no asset: admin-only

    def _allow(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)

    def _get(self, path: str):
        return self.client.get(f"{BASE}/{path}", headers={"x-tenant": str(self.publisher.id)})

    def test_summary_where_missing_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_summary_where_permitted_should_total_own_assets_only(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["metrics"]["plays"]["value"] == 5
        assert body["metrics"]["requests"]["value"] == 6
        assert body["metrics"]["api_calls"]["value"] == 0
        assert body["disclaimers"][0]["code"] == "lower_bound"
        assert body["definitions"]["plays"]

    def test_summary_where_member_without_tenant_header_should_see_own_publishers(self):
        # Arrange
        self._allow()

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["metrics"]["plays"]["value"] == 5

    def test_summary_where_member_of_no_publisher_should_return_zeros(self):
        # Arrange
        outsider = User.objects.create_user(email="outsider@example.com", name="Out")
        self.authenticate_user(outsider)
        self.give_permission(outsider, PermissionChoice.PORTAL_READ_USAGE)

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["metrics"]["plays"]["value"] == 0

    def test_summary_where_asset_of_other_publisher_should_return_404(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"summary/?{RANGE}&asset_id={self.other_asset.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_summary_where_end_before_start_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("summary/?start_date=2026-10-10&end_date=2026-10-01")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_range", response.json()["error_name"])

    def test_timeseries_where_metric_does_not_fit_kind_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"timeseries/?{RANGE}&metric=plays&kind=version_file")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_metric_for_kind", response.json()["error_name"])

    def test_timeseries_where_split_by_publisher_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"timeseries/?{RANGE}&split_by=publisher")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_timeseries_where_split_by_country_should_hide_other_publishers(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"timeseries/?{RANGE}&metric=plays&split_by=country")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        series = response.json()["series"]
        assert [item["key"] for item in series] == ["SA"]
        assert series[0]["points"][2] == {"t": "2026-10-12", "value": 5}

    def test_breakdown_where_by_asset_should_list_own_assets_with_labels(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"breakdown/?{RANGE}&metric=plays&by=asset")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["items"] == [
            {"key": str(self.asset.id), "label": "Asset A", "value": 5, "previous": None}
        ]

    def test_breakdown_where_cached_should_not_query_reports_again(self):
        # Arrange
        self._allow()
        self._get(f"breakdown/?{RANGE}&metric=plays&by=country")
        daily(date(2026, 10, 13), asset_id=self.asset.id, sessions=7)

        # Act
        with CaptureQueriesContext(connection) as queries:
            response = self._get(f"breakdown/?{RANGE}&metric=plays&by=country")

        # Assert
        assert response.json()["items"][0]["value"] == 5
        assert not [query for query in queries.captured_queries if "usage_tracking_traffic" in query["sql"]]

    def test_export_where_permitted_should_return_csv_rows_per_day_and_asset(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"export/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response["Content-Type"].startswith("text/csv")
        assert "usage-2026-10-10-2026-10-16.csv" in response["Content-Disposition"]
        lines = response.content.decode().strip().splitlines()
        assert lines[0] == ("period,asset_id,asset,category,plays,downloads,installs,api_calls,views,requests,bytes")
        assert lines[1:] == [f"2026-10-12,{self.asset.id},Asset A,mushaf,5,0,0,0,0,6,10"]

    def test_endpoints_where_data_grows_should_keep_query_count(self):
        # Arrange
        self._allow()
        counts = []
        for extra in (1, 30):
            cache.clear()
            for index in range(extra):
                daily(date(2026, 10, 10 + index % 7), asset_id=self.asset.id, sessions=1, language=f"l{extra}-{index}")

            # Act
            with CaptureQueriesContext(connection) as queries:
                for path in ("summary/", "timeseries/?split_by=country&", "breakdown/?by=asset&", "export/"):
                    separator = "" if path.endswith("&") else "?"
                    self._get(f"{path}{separator}{RANGE}")
            counts.append(len(queries))

        # Assert
        assert counts[0] == counts[1]
