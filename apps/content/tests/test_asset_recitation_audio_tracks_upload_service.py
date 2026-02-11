from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Resource, Riwayah
from apps.content.services.admin.asset_recitation_audio_tracks_upload_service import (
    bulk_upload_recitation_audio_tracks,
)
from apps.core.tests import BaseTestCase


class TestBulkUploadRecitationAudioTracks(BaseTestCase):
    def test_bulk_upload_where_valid_files_should_create_tracks(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )

        file1 = SimpleUploadedFile("surah_001.mp3", b"fake mp3 content", content_type="audio/mpeg")
        file2 = SimpleUploadedFile("surah_002.mp3", b"fake mp3 content", content_type="audio/mpeg")

        # Act
        stats = bulk_upload_recitation_audio_tracks(asset_id=asset.id, files=[file1, file2])

        # Assert
        self.assertEqual(2, stats["created"])
        self.assertEqual(0, stats["filename_errors"])
        self.assertEqual(0, stats["skipped_duplicates"])
        self.assertEqual(0, stats["other_errors"])

        self.assertTrue(RecitationSurahTrack.objects.filter(asset=asset, surah_number=1).exists())
        self.assertTrue(RecitationSurahTrack.objects.filter(asset=asset, surah_number=2).exists())

    def test_bulk_upload_where_durations_provided_should_store_durations(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )

        file1 = SimpleUploadedFile("surah_001.mp3", b"fake mp3 content", content_type="audio/mpeg")
        file2 = SimpleUploadedFile("surah_002.mp3", b"fake mp3 content", content_type="audio/mpeg")

        durations = {
            "surah_001.mp3": 123456,
            "surah_002.mp3": 654321,
        }

        # Act
        stats = bulk_upload_recitation_audio_tracks(
            asset_id=asset.id, files=[file1, file2], durations_by_filename=durations
        )

        # Assert
        self.assertEqual(2, stats["created"])

        track1 = RecitationSurahTrack.objects.get(asset=asset, surah_number=1)
        track2 = RecitationSurahTrack.objects.get(asset=asset, surah_number=2)

        self.assertEqual(123456, track1.duration_ms)
        self.assertEqual(654321, track2.duration_ms)

    def test_bulk_upload_where_invalid_filename_should_skip_and_report(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )

        valid_file = SimpleUploadedFile("surah_001.mp3", b"fake mp3 content", content_type="audio/mpeg")
        invalid_file = SimpleUploadedFile("invalid_name.mp3", b"fake mp3 content", content_type="audio/mpeg")

        # Act
        stats = bulk_upload_recitation_audio_tracks(asset_id=asset.id, files=[valid_file, invalid_file])

        # Assert
        self.assertEqual(1, stats["created"])
        self.assertEqual(1, stats["filename_errors"])
        self.assertTrue(RecitationSurahTrack.objects.filter(asset=asset, surah_number=1).exists())

    def test_bulk_upload_where_duplicate_in_selection_should_skip_and_report(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )

        file1 = SimpleUploadedFile("surah_001.mp3", b"fake mp3 content", content_type="audio/mpeg")
        file2 = SimpleUploadedFile("another_001.mp3", b"fake mp3 content", content_type="audio/mpeg")

        # Act
        stats = bulk_upload_recitation_audio_tracks(asset_id=asset.id, files=[file1, file2])

        # Assert
        self.assertEqual(1, stats["created"])
        self.assertEqual(1, stats["skipped_duplicates"])
        self.assertIn("duplicate in selection", stats["duplicate_details"][0])

    def test_bulk_upload_where_track_exists_in_db_should_skip_and_report(self):
        # Arrange
        reciter = baker.make(Reciter, name="Test Reciter")
        riwayah = baker.make(Riwayah, name="Test Riwayah")
        asset = baker.make(
            Asset,
            name="test",
            category=Resource.CategoryChoice.RECITATION,
            reciter=reciter,
            riwayah=riwayah,
        )

        # Create existing track
        baker.make(RecitationSurahTrack, asset=asset, surah_number=1)

        file1 = SimpleUploadedFile("surah_001.mp3", b"fake mp3 content", content_type="audio/mpeg")
        file2 = SimpleUploadedFile("surah_002.mp3", b"fake mp3 content", content_type="audio/mpeg")

        # Act
        stats = bulk_upload_recitation_audio_tracks(asset_id=asset.id, files=[file1, file2])

        # Assert
        self.assertEqual(1, stats["created"])
        self.assertEqual(1, stats["skipped_duplicates"])
        self.assertIn("already exists", stats["duplicate_details"][0])
        self.assertTrue(RecitationSurahTrack.objects.filter(asset=asset, surah_number=2).exists())
