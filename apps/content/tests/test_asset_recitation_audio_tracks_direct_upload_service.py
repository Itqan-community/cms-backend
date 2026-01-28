from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from django.utils import timezone
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Riwayah
from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
    AssetRecitationAudioTracksDirectUploadService,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests import BaseTestCase


class TestAssetRecitationAudioTracksDirectUploadService(BaseTestCase):
    def test_start_upload_where_valid_input_should_create_db_record_and_return_upload_payload(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Asset.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        s3 = Mock()
        s3.create_multipart_upload.return_value = {"UploadId": "upload-1"}
        service = AssetRecitationAudioTracksDirectUploadService()
        filename = "anything_001.mp3"

        # Act
        with patch.object(service, "_get_s3_client", return_value=s3):
            result = service.start_upload(asset_id=asset.id, filename=filename)

        # Assert
        self.assertEqual(f"uploads/assets/{asset.id}/recitations/001.mp3", result["key"])
        self.assertEqual("upload-1", result["uploadId"])
        self.assertEqual("audio/mpeg", result["contentType"])
        self.assertEqual(1, result["surahNumber"])

        track = RecitationSurahTrack.objects.get(asset_id=asset.id, surah_number=1)
        self.assertEqual(result["key"], track.audio_file.name)
        self.assertEqual(filename, track.original_filename)
        self.assertIsNone(track.upload_finished_at)

    def test_start_upload_where_duplicate_track_should_abort_multipart_upload_and_raise_itqan_error(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Asset.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        existing_key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        baker.make(
            RecitationSurahTrack,
            asset=asset,
            surah_number=1,
            audio_file=existing_key,
            upload_finished_at=None,
        )
        s3 = Mock()
        s3.create_multipart_upload.return_value = {"UploadId": "upload-dup"}
        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with patch.object(service, "_get_s3_client", return_value=s3):
            with self.assertRaises(ItqanError) as cm:
                service.start_upload(asset_id=asset.id, filename="anything_001.mp3")

        # Assert
        self.assertEqual("duplicate_track", cm.exception.error_name)
        s3.abort_multipart_upload.assert_called_once()

    def test_finish_upload_where_valid_parts_should_update_track_metadata_and_return_payload(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Asset.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        baker.make(
            RecitationSurahTrack,
            asset=asset,
            surah_number=1,
            audio_file=key,
            duration_ms=0,
            size_bytes=0,
            upload_finished_at=None,
        )
        s3 = Mock()
        s3.complete_multipart_upload.return_value = {}
        s3.head_object.return_value = {"ContentLength": 123}
        s3.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"mp3-bytes"))}

        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with (
            patch.object(service, "_get_s3_client", return_value=s3),
            patch(
                "apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service.get_mp3_duration_ms",
                return_value=9876,
            ),
        ):
            result = service.finish_upload(
                key=key,
                upload_id="upload-1",
                parts=[{"ETag": "etag-1", "PartNumber": 1}],
            )

        # Assert
        track = RecitationSurahTrack.objects.get(audio_file=key)
        self.assertEqual(123, track.size_bytes)
        self.assertEqual(9876, track.duration_ms)
        self.assertIsNotNone(track.upload_finished_at)

        self.assertEqual(track.id, result["trackId"])
        self.assertEqual(asset.id, result["assetId"])
        self.assertEqual(1, result["surahNumber"])
        self.assertEqual(123, result["sizeBytes"])
        self.assertEqual(key, result["key"])

    def test_abort_upload_where_incomplete_track_should_delete_db_record(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Asset.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        track = baker.make(
            RecitationSurahTrack,
            asset=asset,
            surah_number=1,
            audio_file=key,
            upload_finished_at=None,
        )

        s3 = Mock()
        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with patch.object(service, "_get_s3_client", return_value=s3):
            result = service.abort_upload(key=key, upload_id="upload-1")

        # Assert
        self.assertFalse(RecitationSurahTrack.objects.filter(id=track.id).exists())
        self.assertTrue(result["aborted"])
        self.assertEqual(1, result["dbRecordsDeleted"])

    def test_cleanup_stuck_uploads_where_initiated_is_older_than_cutoff_should_abort_upload(self):
        # Arrange
        s3 = Mock()
        now = timezone.now()
        old_initiated = now - timedelta(hours=3)  # older than 2 hours (cutoff)
        new_initiated = now - timedelta(minutes=5)
        s3.list_multipart_uploads.return_value = {
            "Uploads": [
                {"Key": "media/uploads/assets/1/recitations/001.mp3", "UploadId": "old-1", "Initiated": old_initiated},
                {"Key": "media/uploads/assets/1/recitations/002.mp3", "UploadId": "new-1", "Initiated": new_initiated},
            ]
        }

        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with (
            patch.object(service, "_get_s3_client", return_value=s3),
            patch.object(service, "abort_upload", return_value={"dbRecordsDeleted": 1}) as abort_upload,
        ):
            result = service.cleanup_stuck_uploads(older_than_hours=2)

        # Assert
        abort_upload.assert_called_once_with(key="media/uploads/assets/1/recitations/001.mp3", upload_id="old-1")
        self.assertEqual(1, result["abortedUploads"])
        self.assertEqual(1, result["dbRecordsCleaned"])
