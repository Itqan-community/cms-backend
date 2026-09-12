import json

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.cache import DEFAULT_FOLDER_CACHE_TOKEN, recitation_ayah_response_cache_key
from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationFolder,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User


class RecitationAyahAudioPublicApiTest(BaseTestCase):
    """Test suite for single-ayah recitation audio public API endpoint."""

    def setUp(self):
        """Set up test fixtures for asset, track, timings, and developer credentials."""
        super().setUp()
        cache.clear()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            restricted_for_tenant=False,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.default_folder = self.asset.recitation_folders.get(is_default=True)
        self.track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            folder=self.default_folder,
            surah_number=2,
            duration_ms=40000,
            size_bytes=640000,
            audio_file=SimpleUploadedFile("s002.mp3", b"dummy-track-content"),
        )
        self.timing = baker.make(
            RecitationAyahTiming,
            track=self.track,
            ayah_key="2:255",
            start_ms=10000,
            end_ms=25000,
            duration_ms=15000,
        )
        self.user = User.objects.create_user(email="dev@example.com", name="Developer User")

    def _authenticate_with_api_key(self, user: User) -> None:
        """Helper to create and attach an API key to the test client."""
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def _grant_access(self, user: User, asset: Asset) -> AssetAccess:
        """Helper to grant approved access for a developer user to a private asset."""
        req = baker.make(
            AssetAccessRequest,
            developer_user=user,
            asset=asset,
            status=AssetAccessRequest.StatusChoice.APPROVED,
        )
        return baker.make(AssetAccess, asset_access_request=req, user=user, asset=asset, expires_at=None)

    def test_get_ayah_audio_where_valid_request_should_return_200_and_audio_metadata(self):
        """Verify that a valid ayah request returns 200 with timing, size, and audio URL."""
        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual("2:255", data["ayah_key"])
        self.assertEqual(2, data["surah_number"])
        self.assertEqual(255, data["ayah_number"])
        self.assertEqual(15000, data["duration_ms"])
        # Estimated size: 640000 * 15000 // 40000 = 240000
        self.assertEqual(240000, data["size_bytes"])
        expected_suffix = f"uploads/assets/{self.asset.id}/recitations/{self.default_folder.id}/002/ayah_255.mp3"
        self.assertTrue(data["audio_url"].endswith(expected_suffix))
        self.assertEqual("public, max-age=300, s-maxage=300", response.headers.get("Cache-Control"))

    def test_get_ayah_audio_where_folder_param_provided_should_resolve_variant_folder(self):
        """Verify that passing folder parameter resolves the variant folder's audio slice."""
        # Arrange - variant folder
        echo_folder = baker.make(
            RecitationFolder,
            asset=self.asset,
            name="With Echo",
            name_en="With Echo",
            slug="with-echo",
            is_default=False,
            is_visible=True,
        )
        echo_track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            folder=echo_folder,
            surah_number=2,
            duration_ms=42000,
            size_bytes=650000,
            audio_file=SimpleUploadedFile("echo_s002.mp3", b"dummy-echo-track"),
        )
        baker.make(
            RecitationAyahTiming,
            track=echo_track,
            ayah_key="2:255",
            start_ms=11000,
            end_ms=27000,
            duration_ms=16000,
        )

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/?folder=with-echo")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        expected_suffix = f"uploads/assets/{self.asset.id}/recitations/{echo_folder.id}/002/ayah_255.mp3"
        self.assertTrue(data["audio_url"].endswith(expected_suffix))
        self.assertEqual(16000, data["duration_ms"])

    def test_get_ayah_audio_where_folder_not_found_should_return_404_folder_not_found(self):
        """Verify that requesting an unresolvable folder returns 404 folder_not_found."""
        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/?folder=nonexistent-folder")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_variant_folder_is_hidden_should_return_404_folder_not_found(self):
        """Verify that requesting a hidden variant folder returns 404 folder_not_found."""
        # Arrange - hidden variant folder
        hidden_folder = baker.make(
            RecitationFolder,
            asset=self.asset,
            name="Hidden Variant",
            name_en="Hidden Variant",
            slug="hidden-variant",
            is_default=False,
            is_visible=False,
        )
        hidden_track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            folder=hidden_folder,
            surah_number=2,
            duration_ms=40000,
            size_bytes=640000,
        )
        baker.make(
            RecitationAyahTiming,
            track=hidden_track,
            ayah_key="2:255",
            start_ms=10000,
            end_ms=25000,
            duration_ms=15000,
        )

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/?folder=hidden-variant")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_default_folder_is_hidden_should_return_404_folder_not_found(self):
        """Verify that requesting default ayah audio when the default folder is hidden returns 404."""
        # Arrange
        self.default_folder.is_visible = False
        self.default_folder.save(update_fields=["is_visible"])

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_asset_not_found_should_return_404_asset_not_found(self):
        """Verify that requesting a non-existent asset ID returns 404 asset_not_found."""
        # Act
        response = self.client.get("/recitations/999999/ayah/2:255/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_ayah_not_found_should_return_404_ayah_not_found(self):
        """Verify that requesting an ayah that has no timing record returns 404 ayah_not_found."""
        # Act - Surah 2 Ayah 1 (not created in timing)
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:1/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("ayah_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_invalid_ayah_key_format_should_return_404_ayah_not_found(self):
        """Verify that malformed or out-of-range ayah keys return 404 ayah_not_found."""
        # Act - Non-canonical ayah keys
        cases = ["invalid", "2", "2:abc", "115:1", "0:1", "1:0"]
        for key in cases:
            response = self.client.get(f"/recitations/{self.asset.id}/ayah/{key}/")
            self.assertEqual(404, response.status_code, f"Expected 404 for key {key}, got {response.status_code}")
            self.assertEqual("ayah_not_found", response.json().get("error_name"))

    def test_get_ayah_audio_where_asset_restricted_for_tenant_should_return_404_asset_not_found(self):
        """Verify that tenant-restricted assets return 404 asset_not_found on public API."""
        # Arrange
        self.asset.restricted_for_tenant = True
        self.asset.save(update_fields=["restricted_for_tenant"])

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json().get("error_name"))

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_audio_where_private_asset_without_api_key_should_return_401(self):
        """Verify that private assets requested without an API key return 401."""
        # Arrange
        self.asset.is_open_access = False
        self.asset.save(update_fields=["is_open_access"])

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json().get("error_name"))

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_audio_where_private_asset_with_key_but_no_grant_should_return_403(self):
        """Verify that private assets requested without an approved grant return 403."""
        # Arrange
        self.asset.is_open_access = False
        self.asset.save(update_fields=["is_open_access"])
        self._authenticate_with_api_key(self.user)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json().get("error_name"))

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_audio_where_private_asset_with_approved_grant_should_return_200(self):
        """Verify that private assets with an approved developer grant return 200 with private cache headers."""
        # Arrange
        self.asset.is_open_access = False
        self.asset.save(update_fields=["is_open_access"])
        self._authenticate_with_api_key(self.user)
        self._grant_access(self.user, self.asset)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("private, no-cache", response.headers.get("Cache-Control"))
        data = response.json()
        self.assertEqual("2:255", data["ayah_key"])

    def test_get_ayah_audio_where_cached_should_serve_from_cache_on_second_request(self):
        """Verify that identical subsequent requests are served from Redis response cache."""
        # Act - 1st request
        first_resp = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")
        self.assertEqual(200, first_resp.status_code, first_resp.content)

        # Verify cached bytes exist
        cache_key = recitation_ayah_response_cache_key(self.asset.id, DEFAULT_FOLDER_CACHE_TOKEN, "2:255")
        cached_raw = cache.get(cache_key)
        self.assertIsNotNone(cached_raw)
        cached_json = json.loads(cached_raw)
        self.assertEqual("2:255", cached_json["ayah_key"])

        # Act - 2nd request (cache hit)
        second_resp = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")
        self.assertEqual(200, second_resp.status_code, second_resp.content)
        self.assertEqual(first_resp.json(), second_resp.json())

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_ayah_audio_where_asset_becomes_private_should_invalidate_cache_and_require_auth(self):
        """Verify that modifying an asset's visibility invalidates cache and requires auth on subsequent requests."""
        # Act 1: Initial public request warms the cache
        resp1 = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")
        self.assertEqual(200, resp1.status_code, resp1.content)

        # Act 2: Admin modifies asset to private
        self.asset.is_open_access = False
        self.asset.save()

        # Act 3: Subsequent unauthenticated request must be rejected (401), not served from stale cache
        resp2 = self.client.get(f"/recitations/{self.asset.id}/ayah/2:255/")
        self.assertEqual(401, resp2.status_code, resp2.content)
        self.assertEqual("authentication_required", resp2.json().get("error_name"))
