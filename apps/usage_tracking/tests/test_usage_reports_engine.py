from datetime import UTC, date, datetime
import itertools
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice, VersionStateChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import (
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficMonthlyUniques,
    UsageApp,
    UsageImportState,
)
from apps.usage_tracking.services import usage_reports
from apps.usage_tracking.services.usage_reports import ReportFilters, admin_scope, breakdown, summary, timeseries

_ray = itertools.count(1)


def daily(day: date, **values) -> TrafficDaily:
    row = {"kind": "audio_surah", "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficDaily.objects.create(day=day, **row)


def hourly(hour: datetime, **values) -> TrafficHourly:
    row = {"kind": "audio_surah", "country": "SA", "channel": "web", "platform": "android", "sessions": 0}
    row.update(values)
    return TrafficHourly.objects.create(hour=hour, **row)


def event(at: datetime, listener: str, **values) -> TrafficEvent:
    row = {
        "kind": "audio_surah",
        "country": "SA",
        "channel": "web",
        "platform": "android",
        "status_class": "full",
        "ua_family": "dalvik",
    }
    row.update(values)
    return TrafficEvent.objects.create(ray_id=f"r{next(_ray)}", occurred_at=at, listener_id=listener, **row)


def at(day: int, hour: int = 12, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=UTC)


WEEK = ReportFilters(start_date=date(2026, 10, 10), end_date=date(2026, 10, 16))


class TestUsageReportsEngine(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.publisher = baker.make(Publisher, name="Pub")
        self.asset = baker.make(Asset, publisher=self.publisher, name="Mushaf A", category=CategoryChoice.MUSHAF)

    def test_summary_where_two_periods_should_total_each_with_change(self):
        # Arrange
        daily(date(2026, 10, 12), asset_id=self.asset.id, sessions=30, requests=50, bytes=900)
        daily(date(2026, 10, 5), asset_id=self.asset.id, sessions=10, requests=12, bytes=100)
        daily(date(2026, 10, 12), asset_id=self.asset.id, kind="version_file", sessions=4, requests=4)
        daily(date(2026, 10, 12), kind="api_call", sessions=7, requests=7, app_id=1, channel="app_identified")
        daily(date(2026, 10, 13), kind="audio_ayah", sessions=2, requests=2, app_id=2, channel="app_identified")
        daily(date(2026, 10, 13), kind="audio_ayah", sessions=1, requests=1, channel="app_unidentified")

        # Act
        result = summary(admin_scope(None), WEEK)

        # Assert
        metrics = result["metrics"]
        assert metrics["plays"] == {"value": 33, "previous": 10, "change": 2.3}
        assert metrics["downloads"]["value"] == 4
        assert metrics["api_calls"]["value"] == 7
        assert metrics["requests"]["value"] == 64
        assert metrics["bytes"] == {"value": 900, "previous": 100, "change": 8.0}
        assert metrics["installs"] == {"value": 0, "previous": 0, "change": None}
        assert result["integrating_apps"]["value"] == 2
        assert result["unidentified_apps"] is True
        assert result["previous_period"] == {"start_date": date(2026, 10, 3), "end_date": date(2026, 10, 9)}
        assert {item["code"] for item in result["disclaimers"]} == {"lower_bound", "uniques_estimated", "hourly_delay"}
        assert set(result["definitions"]) == set(metrics)

    def test_summary_where_listener_returns_on_two_days_should_count_once(self):
        # Arrange
        event(at(11), "L1")
        event(at(12), "L1")
        event(at(12), "L2", kind="audio_ayah", status_class="partial")
        event(at(12), "L3", is_bot=True)
        event(at(12), "L4", status_class="client_error")
        event(at(12), "L5", kind="version_file")
        event(at(4), "L6")

        # Act
        result = summary(admin_scope(None), WEEK)

        # Assert
        assert result["metrics"]["unique_listeners"] == {"value": 2, "previous": 1, "change": 1.0}
        assert result["metrics"]["unique_downloaders"]["value"] == 1
        assert result["uniques_basis"] == "events"

    def test_summary_where_asset_filtered_should_report_latest_version_share(self):
        # Arrange
        language = baker.make(AssetLanguage, asset=self.asset, language="ar")
        old, new = (
            baker.make(AssetVersion, asset=self.asset, asset_language=language, state=VersionStateChoice.PUBLISHED)
            for _ in range(2)
        )
        language.published_version = new
        language.save()
        filters = ReportFilters(start_date=WEEK.start_date, end_date=WEEK.end_date, asset_id=self.asset.id)
        daily(date(2026, 10, 12), asset_id=self.asset.id, kind="version_file", asset_version_id=new.id, sessions=3)
        daily(date(2026, 10, 12), asset_id=self.asset.id, kind="cli_install", asset_version_id=old.id, sessions=1)

        # Act
        result = summary(admin_scope(None), filters)

        # Assert
        assert result["latest_version_share"] == 0.75

    def test_summary_where_range_before_retention_should_use_monthly_uniques(self):
        # Arrange
        filters = ReportFilters(start_date=date(2020, 1, 1), end_date=date(2020, 2, 29))
        for month, count in ((date(2020, 1, 1), 5), (date(2020, 2, 1), 7)):
            TrafficMonthlyUniques.objects.create(month=month, scope="all", scope_id=0, measure="listeners", count=count)

        # Act
        result = summary(admin_scope(None), filters)
        filtered = summary(
            admin_scope(None), ReportFilters(start_date=date(2020, 1, 1), end_date=date(2020, 2, 29), country="SA")
        )

        # Assert
        assert result["uniques_basis"] == "monthly"
        assert result["metrics"]["unique_listeners"]["value"] == 12
        assert filtered["uniques_basis"] == "unavailable"
        assert filtered["metrics"]["unique_listeners"]["value"] is None

    def test_timeseries_where_day_granularity_should_zero_fill(self):
        # Arrange
        daily(date(2026, 10, 11), sessions=5)
        daily(date(2026, 10, 11), sessions=2, country="EG")

        # Act
        result = timeseries(admin_scope(None), WEEK, metric="plays", granularity="day")

        # Assert
        points = result["series"][0]["points"]
        assert len(points) == 7
        assert points[0] == {"t": "2026-10-10", "value": 0}
        assert points[1] == {"t": "2026-10-11", "value": 7}

    def test_timeseries_where_week_and_month_should_start_buckets_on_monday_and_first(self):
        # Arrange
        daily(date(2026, 10, 14), sessions=5)

        # Act
        weekly = timeseries(admin_scope(None), WEEK, metric="plays", granularity="week")
        monthly = timeseries(admin_scope(None), WEEK, metric="plays", granularity="month")

        # Assert
        assert weekly["series"][0]["points"] == [{"t": "2026-10-05", "value": 0}, {"t": "2026-10-12", "value": 5}]
        assert monthly["series"][0]["points"] == [{"t": "2026-10-01", "value": 5}]

    def test_timeseries_where_hourly_should_read_hourly_rollups(self):
        # Arrange
        hourly(at(10, 3), sessions=4)
        filters = ReportFilters(start_date=date(2026, 10, 10), end_date=date(2026, 10, 10))

        # Act
        result = timeseries(admin_scope(None), filters, metric="plays", granularity="hour")

        # Assert
        points = result["series"][0]["points"]
        assert len(points) == 24
        assert points[3] == {"t": "2026-10-10T03:00:00+00:00", "value": 4}

    def test_timeseries_where_split_with_top_one_should_fold_rest_into_other(self):
        # Arrange
        daily(date(2026, 10, 11), sessions=9, country="SA")
        daily(date(2026, 10, 11), sessions=2, country="EG")
        daily(date(2026, 10, 12), sessions=1, country="US")

        # Act
        result = timeseries(admin_scope(None), WEEK, metric="plays", granularity="day", split_by="country", top=1)

        # Assert
        series = {item["key"]: item["points"] for item in result["series"]}
        assert list(series) == ["SA", "other"]
        assert series["other"][1]["value"] == 2
        assert series["other"][2]["value"] == 1

    def test_timeseries_where_unique_split_should_count_distinct_per_bucket(self):
        # Arrange
        event(at(11, 1), "L1", country="SA")
        event(at(11, 2), "L1", country="SA")
        event(at(11, 3), "L2", country="EG")
        event(at(11, 4), "L3", country="US")

        # Act
        result = timeseries(
            admin_scope(None), WEEK, metric="unique_listeners", granularity="day", split_by="country", top=1
        )

        # Assert
        series = {item["key"]: item["points"] for item in result["series"]}
        assert series["EG"][1]["value"] == 1 or series["SA"][1]["value"] == 1
        assert sum(points[1]["value"] for points in series.values()) == 3
        assert series["other"][1]["value"] == 2

    def test_timeseries_where_compare_should_add_aligned_previous_series(self):
        # Arrange
        daily(date(2026, 10, 3), sessions=6)

        # Act
        result = timeseries(admin_scope(None), WEEK, metric="plays", granularity="day", compare=True)

        # Assert
        assert result["previous"][0] == {"t": "2026-10-03", "value": 6}
        assert len(result["previous"]) == 7

    def test_breakdown_where_by_asset_should_label_and_rank(self):
        # Arrange
        other = baker.make(Asset, publisher=self.publisher, name="Font B", category=CategoryChoice.FONT)
        daily(date(2026, 10, 11), asset_id=self.asset.id, sessions=3)
        daily(date(2026, 10, 11), asset_id=other.id, sessions=8)
        daily(date(2026, 10, 2), asset_id=other.id, sessions=1)

        # Act
        result = breakdown(admin_scope(None), WEEK, metric="plays", by="asset", limit=1, compare=True)

        # Assert
        assert result["items"] == [{"key": str(other.id), "label": "Font B", "value": 8, "previous": 0}]
        assert result["other"] == 3
        assert result["total"] == 11

    def test_breakdown_where_hour_of_week_should_shift_to_time_zone(self):
        # Arrange: Monday 2026-10-12 22:00 UTC is Tuesday 01:00 in Riyadh.
        hourly(at(12, 22), sessions=5)

        # Act
        result = breakdown(admin_scope(None), WEEK, metric="plays", by="hour_of_week", tz="Asia/Riyadh")

        # Assert
        assert result["items"] == [{"key": "2-1", "label": None, "value": 5, "previous": None}]

    def test_breakdown_where_by_app_should_label_with_app_name(self):
        # Arrange
        app = UsageApp.objects.create(name="Quran Companion", slug="quran-companion")
        daily(date(2026, 10, 11), kind="api_call", app_id=app.id, sessions=4)

        # Act
        result = breakdown(admin_scope(None), WEEK, metric="api_calls", by="app")

        # Assert
        assert result["items"][0] == {"key": str(app.id), "label": "Quran Companion", "value": 4, "previous": None}

    def test_breakdown_where_unique_metric_should_count_distinct_per_row(self):
        # Arrange
        event(at(11), "L1", country="SA")
        event(at(12), "L1", country="SA")
        event(at(12), "L2", country="SA")
        event(at(12), "L3", country="EG")

        # Act
        result = breakdown(admin_scope(None), WEEK, metric="unique_listeners", by="country")

        # Assert
        assert [(item["key"], item["value"]) for item in result["items"]] == [("SA", 2), ("EG", 1)]
        assert result["other"] is None

    def test_summary_where_called_twice_should_serve_cache(self):
        # Arrange
        daily(date(2026, 10, 12), sessions=1)
        summary(admin_scope(None), WEEK)

        # Act
        with self.assertNumQueries(0):
            result = summary(admin_scope(None), WEEK)

        # Assert
        assert result["metrics"]["plays"]["value"] == 1

    @override_settings(USAGE_REPORTS_CACHE_SECONDS=0)
    def test_summary_where_cache_disabled_should_use_constant_queries(self):
        # Arrange
        UsageImportState.objects.create(key="logpush", last_run_at=at(16))
        for day in range(10, 17):
            daily(date(2026, 10, day), sessions=day, app_id=day)
            event(at(day), f"L{day}")

        # Act
        with self.assertNumQueries(3):
            result = summary(admin_scope(None), WEEK)

        # Assert
        assert result["data_updated_at"] == at(16)

    def test_data_updated_at_where_last_run_failed_should_ignore_it(self):
        # Arrange
        UsageImportState.objects.create(key="logpush", last_run_at=at(16), last_error="boom")
        UsageImportState.objects.create(key="django_foldin", last_run_at=at(15))

        # Act
        with patch.object(usage_reports, "cache_seconds", return_value=0):
            result = summary(admin_scope(None), WEEK)

        # Assert
        assert result["data_updated_at"] == at(15)
