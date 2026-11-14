"""Text-asset reports: CLI installs and updates per version, and access requests."""

from datetime import UTC, date, datetime

from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, AssetLanguage, AssetVersion, CategoryChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.usage_tracking.models import TrafficDaily, TrafficKind
from apps.users.models import User

BASE = "/portal/usage"
RANGE = "start_date=2026-10-10&end_date=2026-10-16"


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": TrafficKind.CLI_INSTALL, "country": "SA", "channel": "cli", "platform": "desktop", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


def request_at(asset: Asset, when: datetime, status: str = AssetAccessRequest.StatusChoice.PENDING):
    access_request = baker.make(AssetAccessRequest, asset=asset, status=status)
    AssetAccessRequest.objects.filter(pk=access_request.pk).update(created_at=when)
    return access_request


class TestTextReports(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = User.objects.create_user(email="member@example.com", name="Member")
        self.publisher = baker.make(Publisher, name="Pub A")
        other_publisher = baker.make(Publisher, name="Pub B")
        baker.make(
            PublisherMember, user=self.user, publisher=self.publisher, status=PublisherMember.StatusChoice.ACTIVE
        )
        self.asset = baker.make(Asset, publisher=self.publisher, name="Mushaf A", category=CategoryChoice.MUSHAF)
        self.other_asset = baker.make(Asset, publisher=other_publisher, name="B", category=CategoryChoice.MUSHAF)
        language = baker.make(AssetLanguage, asset=self.asset, language="ar")
        self.v1 = baker.make(AssetVersion, asset=self.asset, asset_language=language, name="1.0.0")
        self.v2 = baker.make(AssetVersion, asset=self.asset, asset_language=language, name="1.1.0")

    def _allow(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)

    def _get(self, path: str):
        return self.client.get(f"{BASE}/{path}", headers={"x-tenant": str(self.publisher.id)})

    # -- CLI installs and updates per version ---------------------------------------------------

    def test_cli_versions_where_installs_and_updates_should_sum_each_per_version(self):
        # Arrange
        self._allow()
        day = date(2026, 10, 12)
        daily(day, asset_id=self.asset.id, asset_version_id=self.v1.id, sessions=4)
        daily(day, asset_id=self.asset.id, asset_version_id=self.v2.id, sessions=2)
        daily(day, asset_id=self.asset.id, asset_version_id=self.v2.id, kind=TrafficKind.CLI_UPDATE, sessions=5)
        daily(day, asset_id=self.asset.id, asset_version_id=self.v2.id, kind=TrafficKind.VIEW, sessions=99)
        daily(date(2026, 10, 1), asset_id=self.asset.id, asset_version_id=self.v1.id, sessions=50)  # before range
        daily(day, asset_id=self.other_asset.id, asset_version_id=9999, sessions=70)  # other publisher

        # Act
        response = self._get(f"cli-versions/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(i["version_id"], i["version"], i["installs"], i["updates"]) for i in items] == [
            (self.v2.id, "1.1.0", 2, 5),
            (self.v1.id, "1.0.0", 4, 0),
        ]
        assert (items[0]["asset_id"], items[0]["asset"], items[0]["language"]) == (self.asset.id, "Mushaf A", "ar")

    def test_cli_versions_and_access_requests_where_arabic_should_name_assets_in_arabic(self):
        # Arrange
        self.authenticate_user(self.user, language="ar")
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)
        Asset.objects.filter(id=self.asset.id).update(name_en="Mushaf A", name_ar="مصحف أ")
        daily(date(2026, 10, 12), asset_id=self.asset.id, asset_version_id=self.v1.id, sessions=1)
        request_at(self.asset, datetime(2026, 10, 12, tzinfo=UTC))

        # Act
        versions = self._get(f"cli-versions/?{RANGE}")
        requests = self._get(f"access-requests/?{RANGE}")

        # Assert
        self.assertEqual(200, versions.status_code, versions.content)
        assert versions.json()["items"][0]["asset"] == "مصحف أ"
        assert requests.json()["assets"][0]["label"] == "مصحف أ"

    def test_cli_versions_where_other_publishers_asset_should_return_404(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"cli-versions/?{RANGE}&asset_id={self.other_asset.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_cli_versions_where_missing_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self._get(f"cli-versions/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_cli_versions_where_many_versions_should_use_constant_queries(self):
        # Arrange
        self._allow()
        daily(date(2026, 10, 12), asset_id=self.asset.id, asset_version_id=self.v1.id, sessions=1)
        self._get(f"cli-versions/?{RANGE}")  # warm the session and permission lookups
        cache.clear()
        with CaptureQueriesContext(connection) as few:
            self._get(f"cli-versions/?{RANGE}")
        language = baker.make(AssetLanguage, asset=self.asset, language="en")
        for index in range(5):
            version = baker.make(AssetVersion, asset=self.asset, asset_language=language, name=f"2.{index}.0")
            daily(date(2026, 10, 12), asset_id=self.asset.id, asset_version_id=version.id, sessions=1)
        cache.clear()

        # Act
        with CaptureQueriesContext(connection) as many:
            response = self._get(f"cli-versions/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert len(response.json()["items"]) == 6
        assert len(many) == len(few)

    def test_admin_cli_versions_where_not_staff_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/admin/usage/cli-versions/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_admin_cli_versions_where_staff_should_see_every_publisher(self):
        # Arrange
        staff = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)
        self.authenticate_user(staff)
        daily(date(2026, 10, 12), asset_id=self.asset.id, asset_version_id=self.v1.id, sessions=1)
        daily(date(2026, 10, 12), asset_id=self.other_asset.id, asset_version_id=9999, sessions=3)

        # Act
        response = self.client.get(f"/portal/admin/usage/cli-versions/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(i["asset_id"], i["version"], i["installs"]) for i in items] == [
            (self.other_asset.id, None, 3),
            (self.asset.id, "1.0.0", 1),
        ]

    # -- access requests ------------------------------------------------------------------------

    def test_access_requests_where_requests_in_both_periods_should_count_with_statuses_and_change(self):
        # Arrange
        self._allow()
        approved = AssetAccessRequest.StatusChoice.APPROVED
        request_at(self.asset, datetime(2026, 10, 12, 9, tzinfo=UTC))
        request_at(self.asset, datetime(2026, 10, 12, 18, tzinfo=UTC), approved)
        request_at(self.asset, datetime(2026, 10, 16, 23, tzinfo=UTC), approved)
        request_at(self.asset, datetime(2026, 10, 5, tzinfo=UTC))  # previous period
        request_at(self.other_asset, datetime(2026, 10, 12, tzinfo=UTC))  # other publisher

        # Act
        response = self._get(f"access-requests/?{RANGE}&granularity=day")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["total"] == {"value": 3, "previous": 1, "change": 2.0}
        assert body["statuses"] == {"pending": 1, "approved": 2, "rejected": 0}
        points = {point["t"]: point["value"] for point in body["points"]}
        assert (len(points), points["2026-10-12"], points["2026-10-16"], points["2026-10-13"]) == (7, 2, 1, 0)
        assert body["assets"] == [{"key": str(self.asset.id), "label": "Mushaf A", "value": 3}]

    def test_access_requests_where_week_buckets_should_mark_partial_weeks(self):
        # Arrange
        self._allow()
        request_at(self.asset, datetime(2026, 10, 12, tzinfo=UTC))

        # Act
        response = self._get(f"access-requests/?{RANGE}&granularity=week")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert [point["t"] for point in body["points"]] == ["2026-10-05", "2026-10-12"]
        assert body["partial_buckets"] == ["2026-10-05", "2026-10-12"]
        assert body["points"][1]["value"] == 1

    def test_access_requests_where_category_filtered_should_count_that_category_only(self):
        # Arrange
        self._allow()
        font = baker.make(Asset, publisher=self.publisher, name="Font", category=CategoryChoice.FONT)
        request_at(self.asset, datetime(2026, 10, 12, tzinfo=UTC))
        request_at(font, datetime(2026, 10, 12, tzinfo=UTC))

        # Act
        response = self._get(f"access-requests/?{RANGE}&category=font")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["total"]["value"] == 1

    def test_access_requests_where_daily_range_too_long_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("access-requests/?start_date=2026-01-01&end_date=2026-10-16&granularity=day")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_granularity", response.json()["error_name"])

    def test_admin_access_requests_where_not_staff_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(f"/portal/admin/usage/access-requests/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_admin_access_requests_where_publisher_given_should_count_that_publisher_only(self):
        # Arrange
        staff = User.objects.create_user(email="staff@example.com", name="Staff", is_staff=True)
        self.authenticate_user(staff)
        request_at(self.asset, datetime(2026, 10, 12, tzinfo=UTC))
        request_at(self.other_asset, datetime(2026, 10, 12, tzinfo=UTC))

        # Act
        everyone = self.client.get(f"/portal/admin/usage/access-requests/?{RANGE}")
        one = self.client.get(f"/portal/admin/usage/access-requests/?{RANGE}&publisher_id={self.publisher.id}")

        # Assert
        self.assertEqual(200, everyone.status_code, everyone.content)
        assert (everyone.json()["total"]["value"], one.json()["total"]["value"]) == (2, 1)
