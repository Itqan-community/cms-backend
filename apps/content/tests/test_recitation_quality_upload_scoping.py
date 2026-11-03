from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationQuality,
    RecitationSurahTrack,
    Reciter,
    Riwayah,
)
from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
    AssetRecitationAudioTracksDirectUploadService,
)
from apps.content.services.admin.asset_recitation_ayah_timestamps_upload_service import (
    bulk_upload_recitation_ayah_timestamps,
)
from apps.content.services.admin.asset_recitation_json_file_sync_service import sync_asset_recitations_json_file
from apps.content.services.validate_recitation_tracks_upload_service import ValidateRecitationTracksUploadService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class RecitationQualityUploadScopingTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Test Reciter", slug="test-reciter"),
            riwayah=baker.make(Riwayah, name="Test Riwayah"),
        )
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        self.echo_quality = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.service = AssetRecitationAudioTracksDirectUploadService()

    def test_build_key_where_two_qualities_should_produce_distinct_storage_keys(self):
        # Arrange / Act - this is what stops variants overwriting each other in R2
        default_key = self.service._build_key(self.asset.id, self.default_quality.id, 1)
        echo_key = self.service._build_key(self.asset.id, self.echo_quality.id, 1)

        # Assert
        self.assertNotEqual(default_key, echo_key)
        self.assertEqual(default_key, f"uploads/assets/{self.asset.id}/recitations/{self.default_quality.id}/001.mp3")
        self.assertEqual(echo_key, f"uploads/assets/{self.asset.id}/recitations/{self.echo_quality.id}/001.mp3")

    def test_start_upload_where_quality_id_given_should_use_that_quality_in_key(self):
        # Arrange
        s3 = Mock()
        s3.create_multipart_upload.return_value = {"UploadId": "upload-1"}

        # Act
        with patch.object(self.service, "_get_s3_client", return_value=s3):
            result = self.service.start_upload(
                asset_id=self.asset.id, filename="anything_001.mp3", quality_id=self.echo_quality.id
            )

        # Assert
        self.assertEqual(result["qualityId"], self.echo_quality.id)
        self.assertIn(f"/{self.echo_quality.id}/", result["key"])

    def test_start_upload_where_quality_id_omitted_should_use_default_quality(self):
        # Arrange
        s3 = Mock()
        s3.create_multipart_upload.return_value = {"UploadId": "upload-1"}

        # Act
        with patch.object(self.service, "_get_s3_client", return_value=s3):
            result = self.service.start_upload(asset_id=self.asset.id, filename="anything_001.mp3")

        # Assert
        self.assertEqual(result["qualityId"], self.default_quality.id)

    def test_start_upload_where_quality_belongs_to_other_asset_should_raise_quality_not_found(self):
        # Arrange - a quality on a different recitation must not be writable through this asset
        other_asset = baker.make(
            Asset,
            name="other",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Other Reciter", slug="other-reciter"),
            riwayah=baker.make(Riwayah, name="Other Riwayah"),
        )
        foreign_quality = RecitationQuality.objects.create(asset=other_asset, name="Clear", name_en="Clear")
        s3 = Mock()

        # Act / Assert
        with patch.object(self.service, "_get_s3_client", return_value=s3):
            with self.assertRaises(ItqanError) as ctx:
                self.service.start_upload(
                    asset_id=self.asset.id, filename="anything_001.mp3", quality_id=foreign_quality.id
                )

        self.assertEqual(ctx.exception.error_name, "quality_not_found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_finish_upload_where_same_surah_in_two_qualities_should_create_two_tracks(self):
        # Arrange
        s3 = Mock()
        s3.complete_multipart_upload.return_value = {}

        # Act - upload surah 1 into each quality
        with patch.object(self.service, "_get_s3_client", return_value=s3):
            for quality in (self.default_quality, self.echo_quality):
                self.service.finish_upload(
                    key=self.service._build_key(self.asset.id, quality.id, 1),
                    upload_id="upload-1",
                    parts=[{"ETag": "etag-1", "PartNumber": 1}],
                    asset_id=self.asset.id,
                    filename="anything_001.mp3",
                    size_bytes=1024,
                    duration_ms=5000,
                    quality_id=quality.id,
                )

        # Assert - the whole point of the feature
        tracks = RecitationSurahTrack.objects.filter(asset=self.asset, surah_number=1)
        self.assertEqual(tracks.count(), 2)
        self.assertEqual({t.quality_id for t in tracks}, {self.default_quality.id, self.echo_quality.id})

    def test_validate_upload_where_surah_exists_in_other_quality_only_should_report_valid(self):
        # Arrange - surah 1 already uploaded to the default quality
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.default_quality,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
        )
        service = ValidateRecitationTracksUploadService()

        # Act - validating the same surah against the echo quality
        result = service.validate(
            asset_id=self.asset.id, filenames=["anything_001.mp3"], quality_id=self.echo_quality.id
        )

        # Assert - must NOT be skipped: this variant does not have surah 1 yet
        self.assertEqual(result.files[0].status, "valid")

    def test_validate_upload_where_surah_exists_in_same_quality_should_report_skip(self):
        # Arrange
        RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.default_quality,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
        )
        service = ValidateRecitationTracksUploadService()

        # Act
        result = service.validate(
            asset_id=self.asset.id, filenames=["anything_001.mp3"], quality_id=self.default_quality.id
        )

        # Assert
        self.assertEqual(result.files[0].status, "skip")


class RecitationQualityTimingScopingTest(BaseTestCase):
    def setUp(self) -> None:
        self.asset = baker.make(
            Asset,
            name="test",
            category=CategoryChoice.RECITATION,
            reciter=baker.make(Reciter, name="Test Reciter", slug="test-reciter"),
            riwayah=baker.make(Riwayah, name="Test Riwayah"),
        )
        self.default_quality = RecitationQuality.objects.get(asset=self.asset, is_default=True)
        self.echo_quality = RecitationQuality.objects.create(asset=self.asset, name="With echo", name_en="With echo")
        self.default_track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.default_quality,
            surah_number=1,
            audio_file=SimpleUploadedFile("001.mp3", b"x"),
        )
        self.echo_track = RecitationSurahTrack.objects.create(
            asset=self.asset,
            quality=self.echo_quality,
            surah_number=1,
            audio_file=SimpleUploadedFile("001-echo.mp3", b"x"),
        )

    def _timing_file(self, start_ms: int, end_ms: int) -> SimpleUploadedFile:
        # Uploaded timing files carry seconds; the service converts them to ms.
        payload = json.dumps(
            {
                "surah_id": 1,
                "ayahs": [{"ayah_number": 1, "start": start_ms / 1000, "end": end_ms / 1000}],
            }
        ).encode()
        return SimpleUploadedFile("001.json", payload, content_type="application/json")

    def test_bulk_upload_timings_where_quality_given_should_write_only_to_that_quality_track(self):
        # Arrange / Act - echo variants have different offsets, so timings must not leak
        bulk_upload_recitation_ayah_timestamps(
            asset_id=self.asset.id, files=[self._timing_file(500, 1500)], quality_id=self.echo_quality.id
        )

        # Assert
        self.assertEqual(RecitationAyahTiming.objects.filter(track=self.echo_track).count(), 1)
        self.assertEqual(RecitationAyahTiming.objects.filter(track=self.default_track).count(), 0)

    def test_bulk_upload_timings_where_quality_omitted_should_write_to_default_quality_track(self):
        # Arrange / Act
        bulk_upload_recitation_ayah_timestamps(asset_id=self.asset.id, files=[self._timing_file(100, 900)])

        # Assert
        self.assertEqual(RecitationAyahTiming.objects.filter(track=self.default_track).count(), 1)
        self.assertEqual(RecitationAyahTiming.objects.filter(track=self.echo_track).count(), 0)

    def test_bulk_upload_timings_where_quality_unknown_should_raise_quality_not_found(self):
        # Arrange / Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            bulk_upload_recitation_ayah_timestamps(
                asset_id=self.asset.id, files=[self._timing_file(0, 100)], quality_id=999999
            )

        self.assertEqual(ctx.exception.error_name, "quality_not_found")

    def test_sync_json_where_two_qualities_should_write_separate_files_and_versions(self):
        # Arrange / Act
        default_version, default_filename = sync_asset_recitations_json_file(
            asset_id=self.asset.id, quality_id=self.default_quality.id
        )
        echo_version, echo_filename = sync_asset_recitations_json_file(
            asset_id=self.asset.id, quality_id=self.echo_quality.id
        )

        # Assert - one AssetVersion per quality, distinct filenames, no overwrite
        self.assertNotEqual(default_version.pk, echo_version.pk)
        self.assertNotEqual(default_filename, echo_filename)
        self.assertIn(self.default_quality.slug, default_filename)
        self.assertIn(self.echo_quality.slug, echo_filename)

    def test_sync_json_where_run_twice_for_same_quality_should_reuse_one_version(self):
        # Arrange
        first_version, _filename = sync_asset_recitations_json_file(
            asset_id=self.asset.id, quality_id=self.echo_quality.id
        )

        # Act
        second_version, _filename = sync_asset_recitations_json_file(
            asset_id=self.asset.id, quality_id=self.echo_quality.id
        )

        # Assert - repeated syncs update the same row rather than piling up versions
        self.assertEqual(first_version.pk, second_version.pk)

    def test_sync_json_should_contain_only_the_requested_quality_tracks(self):
        # Arrange - give the echo track a timing so the payloads differ
        RecitationAyahTiming.objects.create(track=self.echo_track, ayah_key="1:1", start_ms=5, end_ms=10)

        # Act
        version, _filename = sync_asset_recitations_json_file(asset_id=self.asset.id, quality_id=self.echo_quality.id)
        version.file_url.open("rb")
        payload = json.loads(version.file_url.read().decode())
        version.file_url.close()

        # Assert
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["ayahs_timings"][0]["start_ms"], 5)
