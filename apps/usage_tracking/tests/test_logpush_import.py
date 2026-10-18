from datetime import UTC, datetime, timedelta
import gzip
import json
from unittest.mock import MagicMock, patch

from botocore.exceptions import ReadTimeoutError
from django.test import override_settings
from model_bakery import baker
import pytest

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    LogFileImport,
    TrafficChannel,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficPlatform,
)
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository
from apps.usage_tracking.services import logpush_import
from apps.usage_tracking.services.logpush_import import build_events, import_logpush, touched_hours
from apps.usage_tracking.services.logpush_parser import parse_line
from apps.usage_tracking.services.r2_logs_client import R2LogsClient

NOW = datetime(2026, 10, 18, 12, 10, tzinfo=UTC)
PREFIX = "http/production/"


def _line(ray: str, at: str = "2026-10-18T10:05:00Z", **overrides) -> bytes:
    record = {
        "RayID": ray,
        "EdgeStartTimestamp": at,
        "ClientRequestURI": "/media/uploads/assets/13/recitations/091.mp3",
        "EdgeResponseStatus": 200,
        "EdgeResponseBytes": 100,
        "CacheCacheStatus": "dynamic",
        "ClientIP": "203.0.113.7",
        "ClientCountry": "sa",
        "ClientRequestUserAgent": "Dalvik/2.1.0 (Linux; U; Android 14)",
        "RequestHeaders": {},
    }
    record.update(overrides)
    return json.dumps(record).encode() + b"\n"


_SETTINGS = {
    "ENABLE_USAGE_LOGPUSH_IMPORT": True,
    "USAGE_LOGS_PREFIX": PREFIX,
    "USAGE_LOGS_ACCESS_KEY_ID": "id",
    "USAGE_LOGS_SECRET_ACCESS_KEY": "secret",
    "CLOUDFLARE_R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
    "USAGE_IDENTITY_KEY": "identity",
    "ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES": 5,
    "USAGE_LOGPUSH_MAX_FILES_PER_RUN": 500,
}


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestBuildEvents(BaseTestCase):
    def test_build_events_where_android_audio_should_classify_and_hash(self):
        # Act
        [event] = build_events([parse_line(_line("r1"))])

        # Assert
        assert (event.kind, event.channel, event.platform, event.ua_family) == (
            TrafficKind.AUDIO_SURAH,
            TrafficChannel.APP_UNIDENTIFIED,
            TrafficPlatform.ANDROID,
            "dalvik",
        )
        assert len(event.listener_id) == 64
        assert "203.0.113.7" not in event.listener_id

    def test_build_events_where_version_file_should_resolve_asset_language(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        version = baker.make(AssetVersion, asset=asset)
        uri = f"/media/uploads/assets/{asset.id}/versions/{version.id}/file.zip"

        # Act
        [event] = build_events([parse_line(_line("v1", ClientRequestURI=uri))])

        # Assert
        assert (event.kind, event.asset_id, event.asset_version_id) == (TrafficKind.VERSION_FILE, asset.id, version.id)
        assert event.language == version.asset_language.language

    def test_build_events_where_resolve_slug_should_resolve_asset(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF, slug="hafs-mushaf")

        # Act
        [event] = build_events([parse_line(_line("s1", ClientRequestURI="/packages/resolve/hafs-mushaf/"))])

        # Assert
        assert event.asset_id == asset.id

    def test_build_events_where_cli_install_header_should_hash_install_and_mark_cli(self):
        # Act
        [event] = build_events([parse_line(_line("c1", RequestHeaders={"x-itqan-install-id": "u"}))])

        # Assert
        assert (event.channel, len(event.install_id)) == (TrafficChannel.CLI, 64)

    def test_touched_hours_where_event_near_hour_end_should_include_next_hour(self):
        # Arrange
        events = build_events([parse_line(_line("r1", at="2026-10-18T10:57:00Z"))])

        # Act
        hours = touched_hours(events, timedelta(minutes=5))

        # Assert
        assert hours == {datetime(2026, 10, 18, 10, tzinfo=UTC), datetime(2026, 10, 18, 11, tzinfo=UTC)}


@override_settings(**_SETTINGS)
class TestImportLogpush(BaseTestCase):
    def _patch_client(self, files: dict[str, bytes]):
        client = MagicMock(spec=R2LogsClient)
        client.list_day_prefixes.return_value = sorted({key[: len(PREFIX) + 9] for key in files})
        client.list_keys.side_effect = lambda prefix: sorted(k for k in files if k.startswith(prefix))

        def iter_lines(key: str):
            yield from gzip.decompress(files[key]).splitlines(keepends=True)

        client.iter_lines.side_effect = iter_lines
        return patch.object(logpush_import, logpush_import._build_client.__name__, return_value=client)

    def test_import_logpush_where_disabled_should_do_nothing(self):
        # Arrange
        with self.settings(ENABLE_USAGE_LOGPUSH_IMPORT=False):
            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        assert not LogFileImport.objects.exists()

    def test_import_logpush_where_new_files_should_store_events_and_rebuild_hours(self):
        # Arrange
        files = {
            f"{PREFIX}20261018/a.log.gz": gzip.compress(
                _line("r1") + b"garbage\n" + _line("r2", ClientRequestURI="/.env")
            )
        }

        # Act
        with self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert (result.files_imported, result.events, result.skipped_lines, result.error) == (1, 1, 2, "")
        assert TrafficHourly.objects.get(hour=datetime(2026, 10, 18, 10, tzinfo=UTC)).sessions == 1
        assert TrafficRepository().get_watermark(LOGPUSH_JOB) == datetime(2026, 10, 18, tzinfo=UTC)

    def test_import_logpush_where_rerun_should_skip_imported_files(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))}
        with self._patch_client(files):
            import_logpush(NOW)

            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        assert TrafficEvent.objects.count() == 1

    def test_import_logpush_where_file_corrupt_should_record_error_and_continue(self):
        # Arrange
        files = {
            f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))[:20],
            f"{PREFIX}20261018/b.log.gz": gzip.compress(_line("r2")),
        }

        # Act
        with self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 2
        assert LogFileImport.objects.get(key=f"{PREFIX}20261018/a.log.gz").error != ""
        assert list(TrafficEvent.objects.values_list("ray_id", flat=True)) == ["r2"]

    def test_import_logpush_where_batch_limit_reached_should_keep_watermark_at_pending_day(self):
        # Arrange
        files = {
            f"{PREFIX}20261017/a.log.gz": gzip.compress(_line("r1", at="2026-10-17T10:00:00Z")),
            f"{PREFIX}20261018/b.log.gz": gzip.compress(_line("r2")),
        }

        # Act
        with self.settings(USAGE_LOGPUSH_MAX_FILES_PER_RUN=1), self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 1
        assert TrafficRepository().get_watermark(LOGPUSH_JOB) == datetime(2026, 10, 18, tzinfo=UTC)

    def test_import_logpush_where_lock_held_should_skip(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.try_lock.__name__, return_value=False),
            self._patch_client({}) as build_client,
        ):
            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        build_client.assert_not_called()

    def test_import_logpush_where_record_run_fails_should_still_unlock(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.record_run.__name__, side_effect=RuntimeError("db")),
            patch.object(TrafficRepository, TrafficRepository.unlock.__name__) as unlock,
            self._patch_client({}),
            pytest.raises(RuntimeError),
        ):
            # Act
            import_logpush(NOW)

        # Assert
        unlock.assert_called_once()

    def test_import_logpush_where_rollup_fails_mid_run_should_rebuild_on_next_run(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))}
        with (
            self._patch_client(files),
            patch.object(TrafficRepository, TrafficRepository.rebuild_hour.__name__, side_effect=RuntimeError("db")),
        ):
            first = import_logpush(NOW)

        # Act
        with self._patch_client(files):
            import_logpush(NOW)

        # Assert
        assert "RuntimeError" in first.error
        assert TrafficHourly.objects.get(hour=datetime(2026, 10, 18, 10, tzinfo=UTC)).sessions == 1

    def test_import_logpush_where_read_times_out_should_leave_file_pending(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))}
        with self._patch_client(files) as build_client:
            build_client.return_value.iter_lines.side_effect = ReadTimeoutError(endpoint_url="https://r2")

            # Act
            result = import_logpush(NOW)

        # Assert
        assert "ReadTimeoutError" in result.error
        assert not LogFileImport.objects.exists()

    def test_import_logpush_where_stray_folder_exists_should_ignore_it(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))}
        with self._patch_client(files) as build_client:
            build_client.return_value.list_day_prefixes.return_value = [f"{PREFIX}20261018/", f"{PREFIX}test/"]

            # Act
            result = import_logpush(NOW)

        # Assert
        assert (result.files_imported, result.error) == (1, "")
