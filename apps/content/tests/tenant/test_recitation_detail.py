from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RecitationTracksTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.domain = baker.make(
            "publishers.Domain",
            domain="testpublisher.com",
            publisher=self.publisher,
            is_primary=True,
        )
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
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")

    def test_list_recitation_tracks_should_return_tracks_ordered_by_surah_number(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=2,
            duration_ms=2000,
            size_bytes=1024,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        self.assertEqual(2, len(items))

        # Ordered by surah_number ascending
        self.assertEqual(1, items[0]["surah_number"])
        self.assertEqual("Al-Fatihah", items[0]["surah_name_en"])
        self.assertEqual(2, items[1]["surah_number"])
        self.assertEqual("Al-Baqarah", items[1]["surah_name_en"])

    def test_list_recitation_tracks_should_return_tracks_only_for_request_publisher(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=2,
            duration_ms=2000,
            size_bytes=1024,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        publisher2 = baker.make(Publisher)
        baker.make(
            "publishers.Domain",
            domain="anotherpublisher.com",
            publisher=publisher2,
            is_primary=True,
        )
        resource2 = baker.make(
            Resource,
            publisher=publisher2,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        asset2 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=resource2,
            reciter=baker.make("content.Reciter", name="Test Reciter2"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah2"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=asset2,
            surah_number=3,
            duration_ms=3000,
            size_bytes=2048,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        self.assertEqual(2, len(items))
        self.assertEqual(1, items[0]["surah_number"])
        self.assertEqual(2, items[1]["surah_number"])

    def test_list_recitation_tracks_should_include_audio_url_when_audio_file_exists(self):
        # Arrange
        audio_file = SimpleUploadedFile("test.mp3", b"dummy", content_type="audio/mpeg")
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=audio_file,
        )
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get(f"/tenant/recitation-tracks/{self.asset.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))

        item = items[0]
        self.assertIsNotNone(item["audio_url"])
        self.assertIn("test.mp3", item["audio_url"])

    def test_list_recitation_tracks_for_nonexistent_or_invalid_asset_should_return_404(self):
        self.authenticate_user(self.user, domain=self.domain)
        # Non-existent asset
        response = self.client.get("/tenant/recitation-tracks/999999/")
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

        response = self.client.get(f"/tenant/recitation-tracks/{non_recitation_asset.id}/")
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
            reciter=baker.make("content.Reciter", name="Test Reciter1"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )

        response = self.client.get(f"/tenant/recitation-tracks/{draft_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)
