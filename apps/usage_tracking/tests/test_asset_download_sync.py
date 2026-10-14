from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import override_settings
import pytest

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import AssetDownloadEvent, AssetDownloadHourly, UsageSyncState
from apps.usage_tracking.repositories.asset_downloads import AssetDownloadRepository
from apps.usage_tracking.services import asset_download_sync
from apps.usage_tracking.services.asset_download_sync import (
    build_event_rows,
    build_total_rows,
    fetch_complete,
    plan_hours,
    sync_asset_downloads,
)
from apps.usage_tracking.services.cf_downloads_client import CloudflareDownloadsClient, DatasetLimits

NOW = datetime(2026, 10, 13, 12, 20, tzinfo=UTC)  # last complete hour with 15 min lag: 11:00-12:00
OLDEST = datetime(2026, 9, 12, 13, tzinfo=UTC)
_PLAN = {"lag_minutes": 15, "refresh_hours": 2, "max_slices": 24}


def _hours(*values: int) -> list[datetime]:
    return [datetime(2026, 10, 13, value, tzinfo=UTC) for value in values]


class TestPlanHours:
    def test_plan_hours_where_watermark_current_should_refresh_last_two_hours(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 12, tzinfo=UTC), OLDEST, **_PLAN)

        # Assert
        assert hours == _hours(10, 11)

    def test_plan_hours_where_watermark_behind_should_cover_gap(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 6, tzinfo=UTC), OLDEST, **_PLAN)

        # Assert
        assert hours == _hours(6, 7, 8, 9, 10, 11)

    def test_plan_hours_where_lag_not_elapsed_should_exclude_current_hour(self):
        # Arrange
        now = datetime(2026, 10, 13, 12, 10, tzinfo=UTC)

        # Act
        hours = plan_hours(now, None, datetime(2026, 10, 13, 10, tzinfo=UTC), **_PLAN)

        # Assert
        assert hours == _hours(10)

    def test_plan_hours_where_backlog_exceeds_cap_should_take_oldest_first(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 0, tzinfo=UTC), OLDEST, **{**_PLAN, "max_slices": 3})

        # Assert
        assert hours == _hours(0, 1, 2)

    def test_plan_hours_where_watermark_older_than_retention_should_start_at_oldest_allowed(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 9, 1, tzinfo=UTC), OLDEST, **{**_PLAN, "max_slices": 2})

        # Assert
        assert hours == [OLDEST, OLDEST + timedelta(hours=1)]


class TestFetchComplete:
    def test_fetch_complete_where_page_full_should_split_halves_without_overlap(self):
        # Arrange
        calls: list[tuple[datetime, datetime]] = []

        def fetch(start: datetime, end: datetime, limit: int) -> list[int]:
            calls.append((start, end))
            return [1, 2] if end - start == timedelta(hours=1) else [1]

        start = datetime(2026, 10, 13, 10, tzinfo=UTC)

        # Act
        rows, truncated = fetch_complete(fetch, start, start + timedelta(hours=1), limit=2)

        # Assert
        assert (rows, truncated) == ([1, 1], False)
        assert calls[1] == (start, start + timedelta(minutes=30))
        assert calls[2] == (start + timedelta(minutes=30), start + timedelta(hours=1))

    def test_fetch_complete_where_full_at_floor_should_report_truncated(self):
        # Arrange
        start = datetime(2026, 10, 13, 10, tzinfo=UTC)

        # Act
        _, truncated = fetch_complete(lambda s, e, limit: [0] * limit, start, start + timedelta(minutes=5), limit=3)

        # Assert
        assert truncated is True


class TestBuildRows:
    @pytest.fixture(autouse=True)
    def _secret_key(self, settings):
        settings.SECRET_KEY = "test-secret"

    def test_build_event_rows_where_mixed_paths_should_skip_unmatched_and_normalize(self):
        # Arrange
        events = [
            {
                "datetime": "2026-10-13T10:00:18Z",
                "rayName": "r1",
                "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
                "clientCountryName": "",
                "edgeResponseStatus": 206,
                "clientIP": "203.0.113.7",
            },
            {
                "datetime": "2026-10-13T10:00:19Z",
                "rayName": "r2",
                "clientRequestPath": "/media/uploads/assets/13/cover.png",
                "clientCountryName": "SA",
                "edgeResponseStatus": 200,
                "clientIP": "203.0.113.7",
            },
        ]

        # Act
        rows, unmatched = build_event_rows(events)

        # Assert
        assert unmatched == 1
        assert len(rows) == 1
        assert rows[0].occurred_at == datetime(2026, 10, 13, 10, 0, 18, tzinfo=UTC)
        assert (rows[0].country, rows[0].status_class) == ("XX", "partial")
        assert "203.0.113.7" not in rows[0].client_hash

    def test_build_event_rows_where_client_ip_missing_should_warn(self):
        # Arrange
        events = [
            {
                "datetime": "2026-10-13T10:00:18Z",
                "rayName": "r1",
                "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
                "clientCountryName": "SA",
                "edgeResponseStatus": 200,
                "clientIP": "",
            }
        ]

        # Act
        with patch.object(asset_download_sync.logger, asset_download_sync.logger.warning.__name__) as warning:
            build_event_rows(events)

        # Assert
        warning.assert_called_once()
        assert "clientIP" in warning.call_args.args[0]

    def test_build_event_rows_where_client_ip_missing_should_not_merge_distinct_requests(self):
        # Arrange
        events = [
            {
                "datetime": "2026-10-13T10:00:18Z",
                "rayName": ray,
                "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
                "clientCountryName": "SA",
                "edgeResponseStatus": 200,
                "clientIP": "",
            }
            for ray in ("r1", "r2")
        ]

        # Act
        rows, _ = build_event_rows(events)

        # Assert
        assert rows[0].client_hash != rows[1].client_hash

    def test_build_total_rows_where_sample_interval_above_one_should_flag_sampled(self):
        # Arrange
        totals = [
            {
                "count": 4,
                "avg": {"sampleInterval": 10},
                "sum": {"edgeResponseBytes": 40},
                "dimensions": {
                    "clientRequestPath": "/media/uploads/assets/14/recitations/035.mp3",
                    "clientCountryName": "SA",
                    "edgeResponseStatus": 200,
                },
            }
        ]

        # Act
        rows, sampled = build_total_rows(totals)

        # Assert
        assert sampled is True
        assert (rows[0].requests, rows[0].bytes) == (4, 40)


_SYNC_SETTINGS = {
    "ENABLE_ASSET_DOWNLOAD_SYNC": True,
    "CF_ZONE_ID": "zone-1",
    "CF_API_TOKEN": "token-1",
    "CF_R2_CUSTOM_DOMAIN": "cdn.example.com",
    "SECRET_KEY": "test-secret",
}


def _cf_event(ray: str, at: str) -> dict:
    return {
        "datetime": at,
        "rayName": ray,
        "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
        "clientCountryName": "SA",
        "edgeResponseStatus": 200,
        "clientIP": "203.0.113.7",
    }


def _cf_total(count: int) -> dict:
    return {
        "count": count,
        "avg": {"sampleInterval": 1},
        "sum": {"edgeResponseBytes": count * 100},
        "dimensions": {
            "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
            "clientCountryName": "SA",
            "edgeResponseStatus": 200,
        },
    }


@override_settings(**_SYNC_SETTINGS)
class TestSyncAssetDownloads(BaseTestCase):
    def _patch_client(self, events_by_hour: dict[datetime, list[dict]], fail_hour: datetime | None = None):
        def fetch_events(start: datetime, end: datetime, limit: int) -> list[dict]:
            if start == fail_hour:
                raise RuntimeError("cloudflare down")
            return events_by_hour.get(start, [])

        def fetch_totals(start: datetime, end: datetime, limit: int) -> list[dict]:
            return [_cf_total(len(events_by_hour[start]))] if events_by_hour.get(start) else []

        client = MagicMock(spec=CloudflareDownloadsClient)
        client.fetch_limits.return_value = DatasetLimits(max_page_size=10000, not_older_than=timedelta(hours=4))
        client.fetch_events.side_effect = fetch_events
        client.fetch_totals.side_effect = fetch_totals
        return patch.object(asset_download_sync, asset_download_sync._build_client.__name__, return_value=client)

    @override_settings(ENABLE_ASSET_DOWNLOAD_SYNC=False)
    def test_sync_asset_downloads_where_disabled_should_do_nothing(self):
        # Act
        result = sync_asset_downloads(NOW)

        # Assert
        assert result.hours_synced == 0
        assert not UsageSyncState.objects.exists()

    def test_sync_asset_downloads_where_first_run_should_backfill_retained_hours(self):
        # Arrange
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        with self._patch_client({h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert  (oldest allowed = ceil(12:20 - 4h + 5m) = 09:00 → hours 9, 10, 11)
        assert (result.hours_synced, result.error) == (3, "")
        assert AssetDownloadRepository().get_watermark() == datetime(2026, 10, 13, 12, tzinfo=UTC)
        assert AssetDownloadHourly.objects.get(hour=h11).plays == 1

    def test_sync_asset_downloads_where_rerun_should_not_duplicate(self):
        # Arrange
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        data = {h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}
        with self._patch_client(data):
            sync_asset_downloads(NOW)

            # Act
            sync_asset_downloads(NOW)

        # Assert
        assert AssetDownloadEvent.objects.count() == 1
        assert AssetDownloadHourly.objects.get(hour=h11).requests == 1

    def test_sync_asset_downloads_where_hour_fails_should_keep_watermark_and_record_error(self):
        # Arrange
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        with self._patch_client({h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}, fail_hour=h11):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert  (hours 9 and 10 committed; hour 11 failed and rolled back)
        assert result.hours_synced == 2
        assert "cloudflare down" in result.error
        assert AssetDownloadRepository().get_watermark() == h11
        assert UsageSyncState.objects.get().last_error == result.error
        assert not AssetDownloadHourly.objects.filter(hour=h11).exists()

    def test_sync_asset_downloads_where_lock_held_should_skip(self):
        # Arrange
        with (
            patch.object(AssetDownloadRepository, AssetDownloadRepository.try_lock.__name__, return_value=False),
            self._patch_client({}) as build_client,
        ):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert
        assert result.hours_synced == 0
        build_client.assert_not_called()

    def test_sync_asset_downloads_where_record_run_fails_should_still_unlock(self):
        # Arrange
        with (
            patch.object(
                AssetDownloadRepository, AssetDownloadRepository.record_run.__name__, side_effect=RuntimeError("db")
            ),
            patch.object(AssetDownloadRepository, AssetDownloadRepository.unlock.__name__) as unlock,
            self._patch_client({}),
            pytest.raises(RuntimeError),
        ):
            # Act
            sync_asset_downloads(NOW)

        # Assert
        unlock.assert_called_once()

    @override_settings(ASSET_DOWNLOAD_EVENT_RETENTION_DAYS=1)
    def test_sync_asset_downloads_where_retention_set_should_purge_old_events(self):
        # Arrange
        AssetDownloadEvent.objects.create(
            ray_id="ancient",
            occurred_at=NOW - timedelta(days=3),
            asset_id=1,
            file_kind="surah",
            surah=1,
            country="SA",
            status_class="full",
            client_hash="x" * 64,
        )
        with self._patch_client({}):
            # Act
            sync_asset_downloads(NOW)

        # Assert
        assert not AssetDownloadEvent.objects.filter(ray_id="ancient").exists()
