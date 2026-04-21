from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock, patch

from django.conf import settings
from django.utils import timezone
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, RecitationSurahTrack, Reciter, Riwayah
from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
    AssetRecitationAudioTracksDirectUploadService,
)
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests import BaseTestCase


class TestAssetRecitationAudioTracksDirectUploadService(BaseTestCase):
    def test_start_upload_where_valid_input_should_create_multipart_and_return_payload(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
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
        self.assertEqual(asset.id, result["assetId"])
        self.assertEqual(filename, result["filename"])

        # No DB row created
        self.assertEqual(0, RecitationSurahTrack.objects.filter(asset_id=asset.id).count())

    def test_start_upload_where_valid_filename_should_return_key_and_filename(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
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
        self.assertEqual(result["key"], f"uploads/assets/{asset.id}/recitations/001.mp3")
        self.assertEqual(result["filename"], filename)

        # No DB row created
        self.assertEqual(0, RecitationSurahTrack.objects.filter(asset_id=asset.id).count())

    def test_start_upload_where_valid_input_should_create_multipart_and_return_payload_with_asset_and_filename(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        s3 = Mock()
        s3.create_multipart_upload.return_value = {"UploadId": "upload-2"}
        service = AssetRecitationAudioTracksDirectUploadService()
        filename = "anything_002.mp3"

        # Act
        with patch.object(service, "_get_s3_client", return_value=s3):
            result = service.start_upload(asset_id=asset.id, filename=filename)

        # Assert — assetId and filename returned for use in finish_upload
        self.assertEqual(asset.id, result["assetId"])
        self.assertEqual(filename, result["filename"])
        self.assertEqual(2, result["surahNumber"])
        s3.create_multipart_upload.assert_called_once()

    def test_finish_upload_where_frontend_provides_size_and_duration_should_create_track_without_fallbacks(self):
        # Frontend sends size_bytes and duration_ms — server must use them directly,
        # not compute them from the filesystem or R2.
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        filename = "anything_001.mp3"
        s3 = Mock()
        s3.complete_multipart_upload.return_value = {}
        mock_get_duration = Mock(return_value=9999)

        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with (
            patch.object(service, "_get_s3_client", return_value=s3),
            patch(
                "apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service.get_mp3_duration_ms",
                mock_get_duration,
            ),
        ):
            result = service.finish_upload(
                key=key,
                upload_id="upload-1",
                parts=[{"ETag": "etag-1", "PartNumber": 1}],
                asset_id=asset.id,
                filename=filename,
                size_bytes=5242880,
                duration_ms=1559230,
            )

        # Assert — frontend-provided values stored, no R2 reads triggered
        track = RecitationSurahTrack.objects.get(audio_file=key)
        self.assertEqual(5242880, track.size_bytes)
        self.assertEqual(1559230, track.duration_ms)
        self.assertIsNotNone(track.upload_finished_at)

        self.assertEqual(track.id, result["trackId"])
        self.assertEqual(asset.id, result["assetId"])
        self.assertEqual(1, result["surahNumber"])
        self.assertEqual(5242880, result["sizeBytes"])
        self.assertEqual(key, result["key"])

        s3.head_object.assert_not_called()
        s3.get_object.assert_not_called()
        mock_get_duration.assert_not_called()

    def test_finish_upload_where_size_and_duration_not_provided_should_compute_via_server_fallback(self):
        # Frontend omits size_bytes and duration_ms — server falls back to head_object for
        # size and mutagen (via get_object) for duration.
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        filename = "anything_001.mp3"
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
                asset_id=asset.id,
                filename=filename,
                # size_bytes and duration_ms intentionally omitted
            )

        # Assert — server-computed values stored
        track = RecitationSurahTrack.objects.get(audio_file=key)
        self.assertEqual(123, track.size_bytes)
        self.assertEqual(9876, track.duration_ms)
        self.assertIsNotNone(track.upload_finished_at)

        self.assertEqual(123, result["sizeBytes"])
        s3.head_object.assert_called_once()
        s3.get_object.assert_called_once()

    def test_finish_upload_where_track_already_exists_should_delete_r2_object_and_raise_itqan_error(self):
        # A duplicate finish_upload for the same asset+surah must delete the newly uploaded R2
        # object (to avoid orphaned storage) and raise ItqanError with status 409.
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        key = f"uploads/assets/{asset.id}/recitations/001.mp3"
        filename = "anything_001.mp3"

        # Pre-create a track so the second insert trips the unique constraint
        baker.make(RecitationSurahTrack, asset=asset, surah_number=1, audio_file=key)

        s3 = Mock()
        s3.complete_multipart_upload.return_value = {}
        service = AssetRecitationAudioTracksDirectUploadService()

        # Act & Assert
        with patch.object(service, "_get_s3_client", return_value=s3):
            with self.assertRaises(ItqanError) as ctx:
                service.finish_upload(
                    key=key,
                    upload_id="upload-1",
                    parts=[{"ETag": "etag-1", "PartNumber": 1}],
                    asset_id=asset.id,
                    filename=filename,
                    size_bytes=1024,
                    duration_ms=5000,
                )

        error = ctx.exception
        self.assertEqual("duplicate_track", error.error_name)
        self.assertEqual(409, error.status_code)

        # The orphaned R2 object must be deleted
        r2_key = f"media/{key}"
        s3.delete_object.assert_called_once_with(Bucket=settings.CLOUDFLARE_R2_BUCKET, Key=r2_key)

        # No second DB row created
        self.assertEqual(1, RecitationSurahTrack.objects.filter(asset_id=asset.id, surah_number=1).count())

    def test_abort_upload_should_abort_r2_multipart(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )
        r2_key = f"media/uploads/assets/{asset.id}/recitations/001.mp3"

        s3 = Mock()
        service = AssetRecitationAudioTracksDirectUploadService()

        # Act
        with patch.object(service, "_get_s3_client", return_value=s3):
            result = service.abort_upload(key=r2_key, upload_id="upload-1")

        # Assert
        s3.abort_multipart_upload.assert_called_once()
        call_kwargs = s3.abort_multipart_upload.call_args[1]
        self.assertEqual(r2_key, call_kwargs["Key"])
        self.assertEqual("upload-1", call_kwargs["UploadId"])
        self.assertTrue(result["aborted"])

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
            patch.object(service, "abort_upload", return_value={"aborted": True}) as abort_upload,
        ):
            result = service.cleanup_stuck_uploads(older_than_hours=2)

        # Assert
        abort_upload.assert_called_once_with(key="media/uploads/assets/1/recitations/001.mp3", upload_id="old-1")
        self.assertEqual(1, result["abortedUploads"])
