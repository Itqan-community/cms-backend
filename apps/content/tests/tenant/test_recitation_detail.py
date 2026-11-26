from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetTemplateChoice,
    CategoryChoice,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.core.tests.base import BaseTestCase
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
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")

    def test_list_recitation_tracks_should_return_tracks_ordered_by_surah_number(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            quality=self.asset.recitation_qualities.get(is_default=True),
            surah_number=2,
            duration_ms=2000,
            size_bytes=1024,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            quality=self.asset.recitation_qualities.get(is_default=True),
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
            quality=self.asset.recitation_qualities.get(is_default=True),
            surah_number=2,
            duration_ms=2000,
            size_bytes=1024,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            quality=self.asset.recitation_qualities.get(is_default=True),
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
        asset2 = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=publisher2,
            status=StatusChoice.READY,
            reciter=baker.make("content.Reciter", name="Test Reciter2"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah2"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=asset2,
            quality=asset2.recitation_qualities.get(is_default=True),
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
            quality=self.asset.recitation_qualities.get(is_default=True),
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
        self.assertIn("001", item["audio_url"])

    def test_list_recitation_tracks_for_nonexistent_or_invalid_asset_should_return_404(self):
        self.authenticate_user(self.user, domain=self.domain)
        # Non-existent asset
        response = self.client.get("/tenant/recitation-tracks/999999/")
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

        # Asset with non-RECITATION category should also 404 due to queryset filter
        non_recitation_asset = baker.make(
            Asset,
            category=CategoryChoice.TEXT,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
        )

        response = self.client.get(f"/tenant/recitation-tracks/{non_recitation_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

        # Asset with RECITATION category but DRAFT status should 404
        draft_asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.DRAFT,
            reciter=baker.make("content.Reciter", name="Test Reciter1"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )

        response = self.client.get(f"/tenant/recitation-tracks/{draft_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])


@override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
class RestrictedRecitationTracksTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.domain = baker.make("publishers.Domain", domain="restricted.example.com", publisher=self.publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=False,
            reciter=baker.make("content.Reciter", name="Restricted Reciter"),
            riwayah=baker.make("content.Riwayah", name="Restricted Riwayah"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            quality=self.asset.recitation_qualities.get(is_default=True),
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        self.user = User.objects.create_user(email="listener@example.com", name="Listener")

    def _url(self) -> str:
        return f"/tenant/recitation-tracks/{self.asset.id}/"

    def test_list_recitation_tracks_where_restricted_and_anonymous_should_return_401(self):
        # Arrange
        self.authenticate_user(None, domain=self.domain)

        # Act
        response = self.client.get(self._url())

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])

    def test_list_recitation_tracks_where_restricted_and_no_grant_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get(self._url())

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    def test_list_recitation_tracks_where_restricted_and_access_granted_should_return_200(self):
        # Arrange
        request = baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=self.asset,
            status=AssetAccessRequest.StatusChoice.APPROVED,
        )
        baker.make(AssetAccess, asset_access_request=request, user=self.user, asset=self.asset, expires_at=None)
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get(self._url())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, response.json()["count"])

    def test_list_recitation_tracks_where_open_access_should_add_no_access_query(self):
        # Arrange
        Asset.objects.filter(pk=self.asset.pk).update(is_open_access=True)
        self.authenticate_user(None, domain=self.domain)
        self.client.get(self._url())  # warm the domain cache

        # Act
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(self._url())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse([q for q in ctx.captured_queries if "content_assetaccess" in q["sql"]])
