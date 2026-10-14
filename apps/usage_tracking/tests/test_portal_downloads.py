from datetime import UTC, date, datetime

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import AssetDownloadDaily, AssetDownloadHourly, UsageSyncState
from apps.users.models import User

BASE = "/portal/usage/downloads"
RANGE = "start_date=2026-10-12&end_date=2026-10-13"


def _asset(publisher: Publisher, name: str) -> Asset:
    # Mushaf: recitations need a reciter and text categories a template (DB check constraints).
    return baker.make(Asset, publisher=publisher, name=name, category=CategoryChoice.MUSHAF)


def _daily(asset: Asset, day: date, **overrides) -> AssetDownloadDaily:
    values = {
        "day": day,
        "asset_id": asset.id,
        "file_kind": "surah",
        "surah": 1,
        "asset_version_id": None,
        "country": "SA",
        "status_class": "full",
        "requests": 10,
        "bytes": 1000,
        "plays": 4,
    }
    values.update(overrides)
    return AssetDownloadDaily.objects.create(**values)


class TestPortalDownloads(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="usage-staff@example.com", name="Staff", is_staff=True)
        self.publisher = baker.make(Publisher, name="Pub A")
        self.other_publisher = baker.make(Publisher, name="Pub B")
        self.asset = _asset(self.publisher, "Asset A")
        self.other_asset = _asset(self.other_publisher, "Asset B")
        UsageSyncState.objects.create(key="cf_asset_downloads", watermark=datetime(2026, 10, 13, 12, tzinfo=UTC))

    def _get(self, path: str):
        return self.client.get(f"{BASE}/{path}", headers={"x-tenant": str(self.publisher.id)})

    def _allow(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)

    def test_summary_where_permitted_should_total_own_assets_only(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 12))
        _daily(self.asset, date(2026, 10, 13), file_kind="ayah", status_class="partial", requests=5, plays=1)
        _daily(self.other_asset, date(2026, 10, 13), requests=999)

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["data_until"].startswith("2026-10-13T12:00:00")
        assert body["total"] == {
            "requests_full": 10,
            "requests_partial": 5,
            "requests_other": 0,
            "bytes": 2000,
            "plays": 5,
        }
        assert body["by_file_kind"]["version"]["plays"] == 0
        assert body["by_file_kind"]["ayah"]["requests_partial"] == 5

    def test_summary_where_missing_permission_should_return_403(self):
        # Arrange
        no_perm = User.objects.create_user(email="no-perm@example.com", name="NoPerm", is_staff=False)
        self.authenticate_user(no_perm)

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_summary_where_asset_of_other_publisher_should_return_404(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"summary/?{RANGE}&asset_id={self.other_asset.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_summary_where_member_of_no_publisher_should_return_zeros(self):
        # Arrange
        outsider = User.objects.create_user(email="outsider@example.com", name="Out", is_staff=False)
        self.authenticate_user(outsider)
        self.give_permission(outsider, PermissionChoice.PORTAL_READ_USAGE)
        _daily(self.asset, date(2026, 10, 13))

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["total"]["requests_full"] == 0

    def test_summary_where_end_before_start_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("summary/?start_date=2026-10-13&end_date=2026-10-12")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_range", response.json()["error_name"])

    def test_timeseries_where_daily_should_zero_fill_every_day(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13))

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=day")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        (series,) = response.json()["series"]
        assert series["key"] == "all"
        assert [p["t"] for p in series["points"]] == ["2026-10-12", "2026-10-13"]
        assert [p["requests_full"] for p in series["points"]] == [0, 10]

    def test_timeseries_where_split_by_file_kind_should_return_series_per_kind(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13), file_kind="ayah")

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=day&split_by=file_kind")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        series = {s["key"]: s for s in response.json()["series"]}
        assert set(series) == {"surah", "ayah", "version"}
        assert series["ayah"]["points"][1]["plays"] == 4
        assert series["surah"]["points"][1]["plays"] == 0

    def test_timeseries_where_hourly_should_read_hourly_table_and_fill_48_points(self):
        # Arrange
        self._allow()
        AssetDownloadHourly.objects.create(
            hour=datetime(2026, 10, 13, 10, tzinfo=UTC),
            asset_id=self.asset.id,
            file_kind="surah",
            surah=1,
            country="SA",
            status_class="full",
            requests=3,
            bytes=30,
            plays=2,
        )

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=hour")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        points = response.json()["series"][0]["points"]
        assert len(points) == 48
        assert points[34]["t"].startswith("2026-10-13T10:00:00")
        assert points[34]["plays"] == 2

    def test_timeseries_where_month_range_crosses_year_should_order_months(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2027, 1, 5))

        # Act
        response = self._get("timeseries/?start_date=2026-12-20&end_date=2027-01-10&granularity=month")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        points = response.json()["series"][0]["points"]
        assert [p["t"] for p in points] == ["2026-12-01", "2027-01-01"]
        assert points[1]["requests_full"] == 10

    def test_timeseries_where_hourly_range_over_31_days_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("timeseries/?start_date=2026-09-01&end_date=2026-10-13&granularity=hour")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_too_large", response.json()["error_name"])

    def test_breakdown_where_by_asset_should_rank_by_plays_with_labels(self):
        # Arrange
        self._allow()
        second = _asset(self.publisher, "Asset A2")
        _daily(self.asset, date(2026, 10, 13), plays=1)
        _daily(second, date(2026, 10, 13), plays=9)

        # Act
        response = self._get(f"breakdown/?{RANGE}&by=asset")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["items"]
        assert [(i["key"], i["label"], i["plays"]) for i in items] == [
            (str(second.id), "Asset A2", 9),
            (str(self.asset.id), "Asset A", 1),
        ]

    def test_breakdown_where_by_surah_should_exclude_version_files(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13), surah=2)
        _daily(self.asset, date(2026, 10, 13), file_kind="version", surah=None, asset_version_id=7)

        # Act
        response = self._get(f"breakdown/?{RANGE}&by=surah")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert [i["key"] for i in response.json()["items"]] == ["2"]

    def test_timeseries_where_daily_range_over_ten_years_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("timeseries/?start_date=0001-01-01&end_date=9999-12-30&granularity=day")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_too_large", response.json()["error_name"])

    def test_summary_where_range_over_ten_years_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("summary/?start_date=2000-01-01&end_date=2026-10-13")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_too_large", response.json()["error_name"])

    def test_timeseries_where_end_date_at_calendar_limit_should_return_400_not_500(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("timeseries/?start_date=9999-12-01&end_date=9999-12-31&granularity=month")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_range", response.json()["error_name"])
