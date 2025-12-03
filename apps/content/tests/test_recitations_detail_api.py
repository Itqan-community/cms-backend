from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher


class RecitationTracksTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.recitation_resource,
        )

    def test_list_recitation_tracks_should_return_tracks_ordered_by_surah_number(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=2,
            surah_name="Al-Baqarah",
            surah_name_ar="البقرة",
            chapter_number=2,
            duration_ms=2000,
            size_bytes=1024,
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
        )

        # Act
        response = self.client.get(f"/developers-api/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        self.assertEqual(2, len(items))

        # Ordered by surah_number ascending
        self.assertEqual(1, items[0]["surah_number"])
        self.assertEqual("Al-Fatihah", items[0]["surah_name"])
        self.assertEqual(2, items[1]["surah_number"])
        self.assertEqual("Al-Baqarah", items[1]["surah_name"])

    def test_list_recitation_tracks_should_include_audio_url_when_audio_file_exists(self):
        # Arrange
        audio_file = SimpleUploadedFile("test.mp3", b"dummy", content_type="audio/mpeg")
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=audio_file,
        )

        # Act
        response = self.client.get(f"/developers-api/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))

        item = items[0]
        self.assertIsNotNone(item["audio_url"])
        self.assertIn("test.mp3", item["audio_url"])

    def test_list_recitation_tracks_should_set_audio_url_to_null_when_no_audio_file(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=None,
        )

        # Act
        response = self.client.get(f"/developers-api/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertIsNone(items[0]["audio_url"])

    def test_list_recitation_tracks_for_nonexistent_or_invalid_asset_should_return_404(self):
        # Non-existent asset
        response = self.client.get("/developers-api/recitations/999999/")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with wrong category should also 404 due to queryset filter
        non_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        non_recitation_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
            resource=non_recitation_resource,
        )

        response = self.client.get(f"/developers-api/recitations/{non_recitation_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with RECITATION category but non-READY resource should 404
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        draft_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=draft_resource,
        )

        response = self.client.get(f"/developers-api/recitations/{draft_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)
