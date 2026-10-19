from datetime import UTC, date, datetime

from django.core.cache import cache
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import R2ObjectReadsHourly, TrafficDaily
from apps.users.models import User

BASE = "/portal/admin/usage"
RANGE = "start_date=2026-10-10&end_date=2026-10-16"


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": "audio_surah", "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


class TestAdminUsageReports(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.staff = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)
        self.publisher = baker.make(Publisher, name="Pub A")
        self.other_publisher = baker.make(Publisher, name="Pub B")
        self.asset = baker.make(Asset, publisher=self.publisher, name="Asset A", category=CategoryChoice.MUSHAF)
        self.other_asset = baker.make(
            Asset, publisher=self.other_publisher, name="Asset B", category=CategoryChoice.FONT
        )
        daily(date(2026, 10, 12), asset_id=self.asset.id, sessions=5)
        daily(date(2026, 10, 12), asset_id=self.other_asset.id, sessions=9)
        daily(date(2026, 10, 5), asset_id=self.asset.id, sessions=2)
        daily(date(2026, 10, 12), kind="api_call", sessions=4)

    def test_summary_where_not_staff_should_return_403(self):
        # Arrange
        self.authenticate_user(User.objects.create_user(email="dev@example.com", name="Dev"))

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_summary_where_staff_should_include_every_publisher_and_unassigned_api_calls(self):
        # Arrange
        self.authenticate_user(self.staff)

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        metrics = response.json()["metrics"]
        assert (metrics["plays"]["value"], metrics["api_calls"]["value"]) == (14, 4)

    def test_summary_where_publisher_id_should_narrow_to_that_publisher(self):
        # Arrange
        self.authenticate_user(self.staff)

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}&publisher_id={self.other_publisher.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["metrics"]["plays"]["value"] == 9

    def test_leaderboard_where_by_publisher_should_rank_with_previous_values(self):
        # Arrange
        self.authenticate_user(self.staff)

        # Act
        response = self.client.get(f"{BASE}/leaderboard/?{RANGE}&by=publisher&metric=plays")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["items"] == [
            {"key": str(self.other_publisher.id), "label": "Pub B", "value": 9, "previous": 0},
            {"key": str(self.publisher.id), "label": "Pub A", "value": 5, "previous": 2},
        ]

    def test_timeseries_where_split_by_publisher_should_label_publishers(self):
        # Arrange
        self.authenticate_user(self.staff)

        # Act
        response = self.client.get(f"{BASE}/timeseries/?{RANGE}&metric=plays&split_by=publisher")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert [item["label"] for item in response.json()["series"]] == ["Pub B", "Pub A"]

    def test_reconciliation_where_reads_exceed_edge_should_report_unseen_per_asset_and_day(self):
        # Arrange
        self.authenticate_user(self.staff)
        hour = datetime(2026, 10, 12, 3, tzinfo=UTC)
        R2ObjectReadsHourly.objects.create(
            hour=hour, object_key="a/1", asset_id=self.asset.id, reads=10, edge_requests=4
        )
        R2ObjectReadsHourly.objects.create(
            hour=hour, object_key="a/2", asset_id=self.asset.id, reads=1, edge_requests=3
        )
        R2ObjectReadsHourly.objects.create(hour=hour, object_key="x", asset_id=None, reads=2, edge_requests=0)

        # Act
        response = self.client.get(f"{BASE}/reconciliation/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["total"] == {"reads": 13, "edge_requests": 7, "unseen": 8}
        assert body["assets"][0] == {
            "key": str(self.asset.id),
            "label": "Asset A",
            "reads": 11,
            "edge_requests": 7,
            "unseen": 6,
        }
        assert body["days"][2] == {"t": "2026-10-12", "reads": 13, "edge_requests": 7, "unseen": 8}
        assert len(body["days"]) == 7

    def test_export_where_staff_should_include_publisher_columns(self):
        # Arrange
        self.authenticate_user(self.staff)

        # Act
        response = self.client.get(f"{BASE}/export/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        lines = response.content.decode().strip().splitlines()
        assert lines[0].startswith("period,asset_id,asset,category,publisher_id,publisher,plays")
        assert (
            f"2026-10-12,{self.asset.id},Asset A,mushaf,{self.publisher.id},Pub A,5" in lines[2] + lines[1] + lines[3]
        )
        assert len(lines) == 4
