from __future__ import annotations

import json
from unittest.mock import call, patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.cache import recitation_asset_meta_cache_key, recitation_tracks_cache_key
from apps.content.models import Asset, CategoryChoice, RecitationFolder, RecitationSurahTrack, Reciter, Riwayah
from apps.content.tasks import slice_all_recitation_tracks_task, slice_recitation_track_task
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase

SERVICE_PATH = "apps.content.services.admin.recitation_audio_slicing_service.RecitationAudioSlicingService"


@override_settings(CELERY_TASK_EAGER_PROPAGATES=False)
class TestRecitationAudioSlicingTasks(BaseTestCase):
    def setUp(self) -> None:
        cache.clear()
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Test Reciter", slug="test-reciter"),
            riwayah=baker.make(Riwayah, name="Test Riwayah"),
        )
        self.folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
            duration_ms=5000,
        )

    def _seed_recitation_cache(self) -> None:
        cache.set(recitation_tracks_cache_key(self.asset.id), b"tracks", 60)
        cache.set(recitation_asset_meta_cache_key(self.asset.id), b"meta", 60)

    def _slicing_payload(self) -> dict:
        return {
            "track_id": self.track.id,
            "asset_id": self.asset.id,
            "sliced": 2,
            "keys": [
                f"uploads/assets/{self.asset.id}/recitations/{self.folder.id}/001/ayah_001.mp3",
                f"uploads/assets/{self.asset.id}/recitations/{self.folder.id}/001/ayah_002.mp3",
            ],
        }

    def test_slice_recitation_track_task_where_service_succeeds_should_return_result_and_invalidate_cache(self):
        # Arrange
        self._seed_recitation_cache()
        payload = self._slicing_payload()

        # Act
        with patch(SERVICE_PATH) as mock_service:
            mock_service.return_value.slice_track.return_value = payload
            result = slice_recitation_track_task.apply(args=[self.track.id], throw=False)

        # Assert - delegates to the service and invalidates the asset caches after success
        mock_service.return_value.slice_track.assert_called_once_with(self.track.id)
        self.assertEqual("SUCCESS", result.state)
        self.assertEqual(payload, result.result)
        self.assertIsNone(cache.get(recitation_tracks_cache_key(self.asset.id)))
        self.assertIsNone(cache.get(recitation_asset_meta_cache_key(self.asset.id)))

    def test_slice_recitation_track_task_where_service_fails_should_not_invalidate_cache(self):
        # Arrange
        self._seed_recitation_cache()

        # Act
        with patch(SERVICE_PATH) as mock_service:
            mock_service.return_value.slice_track.side_effect = ItqanError("track_not_found", "missing", 404)
            result = slice_recitation_track_task.apply(args=[self.track.id], throw=False)

        # Assert - no cache invalidation on a failed run
        self.assertEqual("FAILURE", result.state)
        self.assertEqual("track_not_found", result.result.error_name)
        self.assertIsNotNone(cache.get(recitation_tracks_cache_key(self.asset.id)))
        self.assertIsNotNone(cache.get(recitation_asset_meta_cache_key(self.asset.id)))

    def test_slice_recitation_track_task_where_storage_error_should_retry(self):
        # Arrange
        # Act
        with patch(SERVICE_PATH) as mock_service:
            mock_service.return_value.slice_track.side_effect = ItqanError("storage_error", "storage down", 503)
            result = slice_recitation_track_task.apply(args=[self.track.id], throw=False)

        # Assert - initial run plus max_retries (3) eager retries, then permanent failure
        self.assertEqual("FAILURE", result.state)
        self.assertEqual("storage_error", result.result.error_name)
        self.assertEqual(4, mock_service.return_value.slice_track.call_count)

    def test_slice_recitation_track_task_where_permanent_failures_should_not_retry(self):
        # Arrange - validation, missing-track and ffmpeg failures are permanent
        for error_name in ("invalid_ayah_timing", "track_not_found", "slicing_failed"):
            with self.subTest(error_name=error_name):
                # Act
                with patch(SERVICE_PATH) as mock_service:
                    mock_service.return_value.slice_track.side_effect = ItqanError(error_name, "boom", 503)
                    result = slice_recitation_track_task.apply(args=[self.track.id], throw=False)

                # Assert - no retry: exactly one service call, permanent failure
                self.assertEqual("FAILURE", result.state)
                self.assertEqual(error_name, result.result.error_name)
                self.assertEqual(1, mock_service.return_value.slice_track.call_count)

    def test_slice_recitation_track_task_should_return_json_serializable_result(self):
        # Arrange
        payload = self._slicing_payload()

        # Act
        with patch(SERVICE_PATH) as mock_service:
            mock_service.return_value.slice_track.return_value = payload
            result = slice_recitation_track_task.apply(args=[self.track.id], throw=False)

        # Assert - round-trips through JSON without loss
        self.assertEqual(payload, json.loads(json.dumps(result.result)))

    def test_slice_all_should_enqueue_one_child_task_per_track_with_correct_ids(self):
        # Arrange - two extra tracks beside the one from setUp
        for surah_number in (2, 3):
            RecitationSurahTrack.objects.create(
                asset=self.asset,
                folder=self.folder,
                surah_number=surah_number,
                audio_file=SimpleUploadedFile(f"{surah_number:03}.mp3", b"x"),
                duration_ms=1000,
            )
        expected_ids = list(RecitationSurahTrack.objects.values_list("id", flat=True))
        self.assertEqual(3, len(expected_ids))

        # Act
        with patch("apps.content.tasks.slice_recitation_track_task.delay") as mock_delay:
            result = slice_all_recitation_tracks_task.apply(throw=False)

        # Assert - one scheduled child per track, carrying the exact track IDs
        self.assertEqual("SUCCESS", result.state)
        self.assertEqual({"scheduled_count": 3}, result.result)
        self.assertEqual(3, mock_delay.call_count)
        mock_delay.assert_has_calls([call(track_id) for track_id in expected_ids])

    def test_slice_all_where_no_tracks_exist_should_schedule_nothing(self):
        # Arrange
        RecitationSurahTrack.objects.all().delete()

        # Act
        with patch("apps.content.tasks.slice_recitation_track_task.delay") as mock_delay:
            result = slice_all_recitation_tracks_task.apply(throw=False)

        # Assert
        self.assertEqual("SUCCESS", result.state)
        self.assertEqual({"scheduled_count": 0}, result.result)
        mock_delay.assert_not_called()
