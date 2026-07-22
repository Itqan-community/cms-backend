from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from django.test import override_settings
from model_bakery import baker
import pytest

from apps.content.models import Asset
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.repositories.asset_usage import AssetDimensions
from apps.usage_tracking.services import audio_usage_sync
from apps.usage_tracking.services.audio_usage_sync import (
    build_events,
    build_insert_id,
    compute_time_window,
    load_assets_lookup,
    parse_audio_path,
    sync_audio_usage,
)
from apps.usage_tracking.services.cf_analytics_client import CFUsageResult, CFUsageRow, CloudflareAnalyticsClient
from apps.usage_tracking.services.mixpanel_client import MixpanelIngestClient

_OVERRIDE_CF_SETTINGS = {
    "ENABLE_AUDIO_USAGE_SYNC": True,
    "CF_ZONE_ID": "zone-1",
    "CF_API_TOKEN": "token-1",
    "CF_R2_CUSTOM_DOMAIN": "cdn.example.com",
}


def _row(
    count: int = 5,
    path: str = "/media/uploads/assets/2/recitations/001.mp3",
    country: str = "SA",
    device: str = "desktop",
    status: int = 200,
    cache: str = "hit",
    bytes_served: int = 1000,
) -> CFUsageRow:
    return {
        "count": count,
        "dimensions": {
            "clientRequestPath": path,
            "clientCountryName": country,
            "clientDeviceType": device,
            "edgeResponseStatus": status,
            "cacheStatus": cache,
        },
        "sum": {"edgeResponseBytes": bytes_served},
    }


class TestParseAudioPath:
    def test_parse_audio_path_where_path_has_media_prefix_should_return_asset_id_and_surah(self):
        # Act
        parsed = parse_audio_path("/media/uploads/assets/2/recitations/001.mp3")

        # Assert
        assert parsed.asset_id == 2
        assert parsed.surah == 1

    def test_parse_audio_path_where_path_has_no_media_prefix_should_return_asset_id_and_surah(self):
        # Act
        parsed = parse_audio_path("/uploads/assets/42/recitations/114.mp3")

        # Assert
        assert parsed.asset_id == 42
        assert parsed.surah == 114

    def test_parse_audio_path_where_path_is_not_an_audio_path_should_return_none(self):
        # Act / Assert
        assert parse_audio_path("/uploads/reciters/2/image.png") is None

    def test_parse_audio_path_where_path_from_upload_helper_should_match(self):
        # Arrange
        from apps.core.uploads import upload_to_recitation_surah_track_files

        instance = MagicMock(asset_id=7, surah_number=2)

        # Act
        path = upload_to_recitation_surah_track_files(instance, "track.mp3")
        parsed = parse_audio_path("/media/" + path)

        # Assert
        assert parsed is not None
        assert parsed.asset_id == 7
        assert parsed.surah == 2


class TestComputeTimeWindow:
    def test_compute_time_window_where_now_just_past_boundary_should_return_last_elapsed_6h_window(self):
        # Arrange
        now = datetime(2026, 7, 18, 6, 5, tzinfo=UTC)

        # Act
        window = compute_time_window(now)

        # Assert
        assert window.start == datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
        assert window.end == datetime(2026, 7, 18, 6, 0, tzinfo=UTC)

    def test_compute_time_window_where_now_is_non_utc_tz_should_return_window_in_utc(self):
        # Arrange
        riyadh = timezone(timedelta(hours=3))
        now = datetime(2026, 7, 18, 9, 5, tzinfo=riyadh)  # 06:05 UTC

        # Act
        window = compute_time_window(now)

        # Assert
        assert window.start == datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
        assert window.end == datetime(2026, 7, 18, 6, 0, tzinfo=UTC)

    def test_compute_time_window_where_now_is_mid_window_should_return_prior_boundary_window(self):
        # Arrange
        now = datetime(2026, 7, 18, 10, 30, tzinfo=UTC)

        # Act
        window = compute_time_window(now)

        # Assert
        assert window.start == datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
        assert window.end == datetime(2026, 7, 18, 6, 0, tzinfo=UTC)

    def test_compute_time_window_where_window_hours_does_not_divide_day_should_raise(self):
        # Arrange
        now = datetime(2026, 7, 18, 10, 30, tzinfo=UTC)

        # Act / Assert
        with pytest.raises(ValueError):
            compute_time_window(now, window_hours=5)


class TestBuildInsertId:
    def test_build_insert_id_where_inputs_are_identical_should_return_same_id(self):
        # Arrange
        window_start = datetime(2026, 7, 18, 0, 0, tzinfo=UTC)

        # Act
        id1 = build_insert_id(window_start, "/a.mp3", "SA", "desktop", 200, "hit")
        id2 = build_insert_id(window_start, "/a.mp3", "SA", "desktop", 200, "hit")

        # Assert
        assert id1 == id2
        assert len(id1) == 36

    def test_build_insert_id_where_any_dimension_changes_should_return_different_id(self):
        # Arrange
        window_start = datetime(2026, 7, 18, 0, 0, tzinfo=UTC)

        # Act
        base = build_insert_id(window_start, "/a.mp3", "SA", "desktop", 200, "hit")

        # Assert
        assert base != build_insert_id(window_start, "/b.mp3", "SA", "desktop", 200, "hit")
        assert base != build_insert_id(window_start, "/a.mp3", "US", "desktop", 200, "hit")
        assert base != build_insert_id(window_start, "/a.mp3", "SA", "mobile", 200, "hit")
        assert base != build_insert_id(window_start, "/a.mp3", "SA", "desktop", 206, "hit")
        assert base != build_insert_id(window_start, "/a.mp3", "SA", "desktop", 200, "miss")


class TestBuildEvents:
    def setup_method(self):
        self.window_start = datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
        self.window_end = datetime(2026, 7, 18, 6, 0, tzinfo=UTC)

    def test_build_events_where_any_row_should_set_empty_distinct_id(self):
        # Act
        events = build_events([_row()], {}, self.window_start, self.window_end)

        # Assert
        assert events[0]["properties"]["distinct_id"] == ""

    def test_build_events_where_asset_is_in_lookup_should_carry_publisher_and_reciter_info(self):
        # Arrange
        lookup = {
            2: AssetDimensions(
                name="Test Asset",
                publisher_id=7,
                publisher_name="Test Pub",
                reciter="Test Reciter",
                riwayah="Hafs",
                qiraah="Asim",
            )
        }

        # Act
        events = build_events([_row()], lookup, self.window_start, self.window_end)
        props = events[0]["properties"]

        # Assert
        assert props["enriched"] is True
        assert props["asset_id"] == 2
        assert props["asset_name"] == "Test Asset"
        assert props["surah"] == 1
        assert props["publisher_id"] == 7
        assert props["publisher_name"] == "Test Pub"
        assert props["reciter"] == "Test Reciter"

    def test_build_events_where_asset_is_not_in_lookup_should_mark_event_unenriched(self):
        # Act
        events = build_events([_row()], {}, self.window_start, self.window_end)
        props = events[0]["properties"]

        # Assert
        assert props["enriched"] is False
        assert props["publisher_id"] is None

    def test_build_events_where_row_has_count_and_bytes_should_carry_them_through(self):
        # Act
        events = build_events([_row(count=13, bytes_served=8809)], {}, self.window_start, self.window_end)
        props = events[0]["properties"]

        # Assert
        assert props["request_count"] == 13
        assert props["bytes"] == 8809

    def test_build_events_where_cache_status_varies_should_set_is_cache_hit_accordingly(self):
        # Act
        hit = build_events([_row(cache="hit")], {}, self.window_start, self.window_end)[0]
        miss = build_events([_row(cache="miss")], {}, self.window_start, self.window_end)[0]

        # Assert
        assert hit["properties"]["is_cache_hit"] is True
        assert miss["properties"]["is_cache_hit"] is False

    def test_build_events_where_window_given_should_set_time_and_bounds_as_epoch_seconds(self):
        # Act
        events = build_events([_row()], {}, self.window_start, self.window_end)
        props = events[0]["properties"]

        # Assert
        assert props["time"] == int(self.window_start.timestamp())
        assert props["window_start"] == int(self.window_start.timestamp())
        assert props["window_end"] == int(self.window_end.timestamp())

    def test_build_events_where_window_given_should_set_iso_time_props_in_24h_utc(self):
        # Act
        events = build_events([_row()], {}, self.window_start, self.window_end)
        props = events[0]["properties"]

        # Assert
        assert props["window_start_iso"] == "2026-07-18 00:00 UTC"
        assert props["window_end_iso"] == "2026-07-18 06:00 UTC"
        assert props["event_time_iso"] == props["window_start_iso"]

    def test_build_events_where_same_rows_rebuilt_should_keep_insert_id_stable(self):
        # Act
        events1 = build_events([_row()], {}, self.window_start, self.window_end)
        events2 = build_events([_row()], {}, self.window_start, self.window_end)

        # Assert
        assert events1[0]["properties"]["$insert_id"] == events2[0]["properties"]["$insert_id"]


class TestLoadAssetLookup(BaseTestCase):
    def test_load_assets_lookup_where_ids_are_empty_should_return_empty_dict_without_query(self):
        # Act / Assert
        with self.assertNumQueries(0):
            assert load_assets_lookup(set()) == {}

    def test_load_assets_lookup_where_assets_match_should_return_dimensional_fields(self):
        # Arrange
        publisher = baker.make("publishers.Publisher", name="Test Pub")
        reciter = baker.make("content.Reciter", name="Test Reciter")
        riwayah = baker.make("content.Riwayah", name="Test Riwayah")
        asset = baker.make(
            Asset,
            publisher=publisher,
            name="Test Asset",
            category="recitation",
            reciter=reciter,
            riwayah=riwayah,
            license="CC0",
        )

        # Act
        lookup = load_assets_lookup({asset.id})

        # Assert
        assert lookup[asset.id].name == "Test Asset"
        assert lookup[asset.id].publisher_id == publisher.id
        assert lookup[asset.id].publisher_name == "Test Pub"
        assert lookup[asset.id].reciter == "Test Reciter"
        assert lookup[asset.id].riwayah == "Test Riwayah"

    def test_load_assets_lookup_where_asset_id_missing_should_be_absent_from_lookup(self):
        # Act
        lookup = load_assets_lookup({999999})

        # Assert
        assert lookup == {}


class TestSyncAudioUsage:
    def test_sync_audio_usage_where_feature_flag_disabled_should_be_noop(self):
        # Arrange
        with override_settings(ENABLE_AUDIO_USAGE_SYNC=False):
            # Act / Assert
            assert sync_audio_usage() == 0

    def test_sync_audio_usage_where_cf_settings_missing_should_be_noop(self):
        # Arrange
        with (
            override_settings(
                ENABLE_AUDIO_USAGE_SYNC=True,
                CF_ZONE_ID="",
                CF_API_TOKEN="",
                CF_R2_CUSTOM_DOMAIN="",
            ),
            patch.object(audio_usage_sync, audio_usage_sync._build_cf_client.__name__) as mock_build_cf,
        ):
            # Act
            result = sync_audio_usage()

            # Assert
            assert result == 0
            mock_build_cf.assert_not_called()

    def test_sync_audio_usage_where_cloudflare_returns_no_rows_should_skip_mixpanel_import(self):
        # Arrange
        mock_cf_client = MagicMock()
        mock_cf_client.fetch_audio_usage.return_value = CFUsageResult(rows=[], truncated=False)

        with (
            override_settings(**_OVERRIDE_CF_SETTINGS),
            patch.object(audio_usage_sync, CloudflareAnalyticsClient.__name__, return_value=mock_cf_client),
            patch.object(audio_usage_sync, load_assets_lookup.__name__) as mock_load_lookup,
            patch.object(audio_usage_sync, MixpanelIngestClient.__name__) as mock_ingest_cls,
        ):
            # Act
            result = sync_audio_usage()

            # Assert
            assert result == 0
            mock_load_lookup.assert_not_called()
            mock_ingest_cls.return_value.import_events.assert_not_called()

    def test_sync_audio_usage_where_cf_result_is_truncated_should_log_warning(self):
        # Arrange
        mock_cf_client = MagicMock()
        mock_cf_client.fetch_audio_usage.return_value = CFUsageResult(rows=[_row()], truncated=True)
        mock_ingest_client = MagicMock()
        mock_ingest_client.import_events.return_value = 1

        with (
            override_settings(**_OVERRIDE_CF_SETTINGS),
            patch.object(audio_usage_sync, CloudflareAnalyticsClient.__name__, return_value=mock_cf_client),
            patch.object(audio_usage_sync, load_assets_lookup.__name__, return_value={}),
            patch.object(audio_usage_sync, MixpanelIngestClient.__name__, return_value=mock_ingest_client),
            patch.object(audio_usage_sync, "logger") as mock_logger,
        ):
            # Act
            sync_audio_usage()

            # Assert
            warning_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
            assert any("hit the query limit" in message for message in warning_messages)

    def test_sync_audio_usage_where_cloudflare_returns_rows_should_enrich_and_import_them(self):
        # Arrange
        mock_cf_client = MagicMock()
        mock_cf_client.fetch_audio_usage.return_value = CFUsageResult(rows=[_row()], truncated=False)
        mock_ingest_client = MagicMock()
        mock_ingest_client.import_events.return_value = 1

        with (
            override_settings(**_OVERRIDE_CF_SETTINGS),
            patch.object(audio_usage_sync, CloudflareAnalyticsClient.__name__, return_value=mock_cf_client),
            patch.object(audio_usage_sync, load_assets_lookup.__name__, return_value={}) as mock_load_lookup,
            patch.object(audio_usage_sync, MixpanelIngestClient.__name__, return_value=mock_ingest_client),
        ):
            # Act
            result = sync_audio_usage()

            # Assert
            assert result == 1
            mock_load_lookup.assert_called_once_with({2})
            mock_ingest_client.import_events.assert_called_once()
            sent_events = mock_ingest_client.import_events.call_args[0][0]
            assert len(sent_events) == 1
