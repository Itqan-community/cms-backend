"""
Tests for ITQ-7: per-ayah audio file reference storage.

Covers:
  1. RecitationAudioSlicingService persists audio_file + size_bytes on
     RecitationAyahTiming after a successful slice-and-upload.
  2. RecitationService.get_ayah_audio_data uses timing.size_bytes (exact)
     when available, and falls back to the proportional estimate otherwise.
  3. RecitationAyahTiming inherits DeleteFilesOnDeleteMixin so its audio_file
     is cleaned up on delete.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import boto3
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
    StatusChoice,
)
from apps.content.services.admin.recitation_audio_slicing_service import RecitationAudioSlicingService
from apps.content.services.recitation import RecitationService
from apps.core.mixins.storage import DeleteFilesOnDeleteMixin
from apps.core.tests.base import BaseTestCase

SOURCE_BODY = b"fake-source-mp3-bytes"


class TestSlicingServicePersistsAyahAudioReference(BaseTestCase):
    """RecitationAudioSlicingService must write audio_file + size_bytes to the DB."""

    def setUp(self) -> None:
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Slicer Reciter", slug="slicer-reciter"),
            riwayah=baker.make(Riwayah, name="Slicer Riwayah"),
        )
        self.folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.folder,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
            duration_ms=5000,
        )
        self.timing = RecitationAyahTiming.objects.create(track=self.track, ayah_key="1:1", start_ms=0, end_ms=2000)
        self.service = RecitationAudioSlicingService()
        self.s3 = boto3.client("s3", region_name="us-east-1")
        client_patcher = patch.object(self.service, "_get_s3_client", return_value=self.s3)
        client_patcher.start()
        self.addCleanup(client_patcher.stop)
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=f"media/{self.track.audio_file.name}",
            Body=SOURCE_BODY,
        )

    def _fake_ffmpeg(self, output_body: bytes = b"ayah-mp3-bytes"):
        def fake_run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(output_body)
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        return fake_run

    def test_slice_track_where_slice_succeeds_should_persist_audio_file_and_size_bytes_on_timing(self):
        # Arrange
        ayah_bytes = b"ayah-mp3-bytes-1234"

        # Act
        with patch("subprocess.run", side_effect=self._fake_ffmpeg(ayah_bytes)):
            self.service.slice_track(self.track.id)

        # Assert - timing row updated with the R2 key and exact byte count
        self.timing.refresh_from_db()
        expected_key = f"uploads/assets/{self.asset.id}/recitations/{self.folder.id}/001/ayah_001.mp3"
        self.assertEqual(expected_key, self.timing.audio_file.name)
        self.assertEqual(len(ayah_bytes), self.timing.size_bytes)

    def test_slice_track_where_multiple_ayahs_should_persist_each_timing_independently(self):
        # Arrange
        timing2 = RecitationAyahTiming.objects.create(track=self.track, ayah_key="1:2", start_ms=2000, end_ms=4000)
        ayah1_bytes = b"ayah1" * 100
        ayah2_bytes = b"ayah2" * 200
        call_count = 0

        def _fake_ffmpeg_multi(cmd, **kwargs):
            nonlocal call_count
            content = ayah1_bytes if call_count == 0 else ayah2_bytes
            call_count += 1
            Path(cmd[-1]).write_bytes(content)
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        # Act
        with patch("subprocess.run", side_effect=_fake_ffmpeg_multi):
            result = self.service.slice_track(self.track.id)

        # Assert
        self.assertEqual(2, result["sliced"])
        self.timing.refresh_from_db()
        timing2.refresh_from_db()
        self.assertEqual(len(ayah1_bytes), self.timing.size_bytes)
        self.assertEqual(len(ayah2_bytes), timing2.size_bytes)
        self.assertIsNotNone(self.timing.audio_file.name)
        self.assertIsNotNone(timing2.audio_file.name)

    def test_slice_track_where_upload_fails_should_not_update_timing(self):
        # Arrange
        from botocore.exceptions import ClientError

        put_error = ClientError({"Error": {"Code": "InternalError", "Message": "boom"}}, "put_object")

        # Act
        with (
            patch("subprocess.run", side_effect=self._fake_ffmpeg()),
            patch.object(self.s3, "put_object", side_effect=put_error),
        ):
            from apps.core.ninja_utils.errors import ItqanError

            with self.assertRaises(ItqanError) as ctx:
                self.service.slice_track(self.track.id)

        # Assert - storage error raised, timing remains unpopulated
        self.assertEqual("storage_error", ctx.exception.error_name)
        self.timing.refresh_from_db()
        self.assertFalse(self.timing.audio_file.name)
        self.assertEqual(0, self.timing.size_bytes)


class TestGetAyahAudioDataSizeBytes(BaseTestCase):
    """RecitationService.get_ayah_audio_data must prefer timing.size_bytes when set."""

    def setUp(self) -> None:
        # Asset must be READY so get_asset_object returns it (status filter in repo)
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            reciter=baker.make(Reciter, name="Service Reciter", slug="service-reciter"),
            riwayah=baker.make(Riwayah, name="Service Riwayah"),
        )
        self.folder = RecitationFolder.objects.get(asset=self.asset, is_default=True)
        self.track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            folder=self.folder,
            surah_number=2,
            audio_file=SimpleUploadedFile("002.mp3", b"x"),
            duration_ms=10000,
            size_bytes=100000,
        )
        self.service = RecitationService()

    def test_get_ayah_audio_data_where_timing_has_size_bytes_should_use_exact_value(self):
        # Arrange
        timing = RecitationAyahTiming.objects.create(
            track=self.track,
            ayah_key="2:1",
            start_ms=0,
            end_ms=3000,
        )
        # Simulate what the slicer writes: exact file size recorded on the timing row
        RecitationAyahTiming.objects.filter(pk=timing.pk).update(size_bytes=12345)

        # Act
        data = self.service.get_ayah_audio_data(
            asset_id=self.asset.id,
            ayah_key="2:1",
        )

        # Assert - exact size from timing row, not the proportional estimate
        self.assertEqual(12345, data["size_bytes"])

    def test_get_ayah_audio_data_where_timing_has_no_size_bytes_should_fall_back_to_proportional_estimate(self):
        # Arrange - size_bytes=0 (pre-slicing state)
        RecitationAyahTiming.objects.create(
            track=self.track,
            ayah_key="2:2",
            start_ms=0,
            end_ms=5000,
        )
        # track: duration_ms=10000, size_bytes=100000; ayah: duration_ms=5000
        # expected estimate: 100000 * 5000 // 10000 = 50000

        # Act
        data = self.service.get_ayah_audio_data(
            asset_id=self.asset.id,
            ayah_key="2:2",
        )

        # Assert - proportional fallback
        self.assertEqual(50000, data["size_bytes"])

    def test_get_ayah_audio_data_where_track_has_no_size_bytes_should_return_none(self):
        # Arrange - track has no size, timing has no size
        RecitationSurahTrack.objects.filter(pk=self.track.pk).update(size_bytes=0)
        self.track.refresh_from_db()
        RecitationAyahTiming.objects.create(
            track=self.track,
            ayah_key="2:3",
            start_ms=0,
            end_ms=1000,
        )

        # Act
        data = self.service.get_ayah_audio_data(
            asset_id=self.asset.id,
            ayah_key="2:3",
        )

        # Assert - no size info available from either source
        self.assertIsNone(data["size_bytes"])


class TestRecitationAyahTimingDeleteFilesOnDeleteMixin(BaseTestCase):
    """RecitationAyahTiming must inherit DeleteFilesOnDeleteMixin."""

    def test_recitation_ayah_timing_where_class_checked_should_be_subclass_of_delete_files_on_delete_mixin(self):
        # Arrange / Act / Assert - static structural check, no DB needed
        self.assertTrue(issubclass(RecitationAyahTiming, DeleteFilesOnDeleteMixin))

    def test_recitation_ayah_timing_where_deleted_should_delete_audio_file_from_storage(self):
        # Arrange
        asset = baker.make(
            Asset,
            name="del-test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Del Reciter", slug="del-reciter"),
            riwayah=baker.make(Riwayah, name="Del Riwayah"),
        )
        folder = RecitationFolder.objects.get(asset=asset, is_default=True)
        track = RecitationSurahTrack.objects.create(
            asset=asset,
            folder=folder,
            surah_number=3,
            audio_file=SimpleUploadedFile("003.mp3", b"x"),
            duration_ms=2000,
        )
        timing = RecitationAyahTiming.objects.create(track=track, ayah_key="3:1", start_ms=0, end_ms=1000)
        # Attach a mock audio_file (as if the slicer ran)
        mock_file = MagicMock()
        mock_file.name = "uploads/assets/1/recitations/1/003/ayah_001.mp3"
        timing.audio_file = mock_file

        # Act - invoke the same logic the post_delete signal calls
        with patch.object(mock_file, "delete") as mock_delete:
            for field in RecitationAyahTiming._iter_file_fields():
                f = getattr(timing, field.name, None)
                if f and getattr(f, "name", ""):
                    f.delete(save=False)

        # Assert - storage delete was called for the audio_file field
        mock_delete.assert_called_once_with(save=False)
