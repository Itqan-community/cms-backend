import unittest

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.cache import recitation_response_cache_key
from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    CategoryChoice,
    RecitationAyahTiming,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.core.ninja_utils.paginations import (
    DEFAULT_PAGE_SIZE,
    PUBLIC_RECITATION_MAX_PAGE_SIZE,
    PublicRecitationPagination,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User


class RecitationTracksTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=True,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

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
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/")

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
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))

        item = items[0]
        self.assertIsNotNone(item["audio_url"])
        self.assertIn(f"/assets/{self.asset.id}/recitations/001", item["audio_url"])

    def test_list_recitation_tracks_for_nonexistent_or_invalid_asset_should_return_404(self):
        self.authenticate_client(self.app)
        # Non-existent asset
        response = self.client.get("/recitations/999999/")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with wrong category should also 404 due to queryset filter
        non_recitation_asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
        )

        response = self.client.get(f"/recitations/{non_recitation_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with RECITATION category but DRAFT status should 404
        draft_asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.DRAFT,
            reciter=baker.make("content.Reciter", name="Test Reciter1"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah1"),
        )

        response = self.client.get(f"/recitations/{draft_asset.id}/")
        self.assertEqual(404, response.status_code, response.content)

    def test_list_recitation_tracks_where_timings_exist_should_embed_timings(self):
        # Arrange
        track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
        )
        # Create two ayah timings for the track
        baker.make(
            RecitationAyahTiming,
            track=track,
            ayah_key="1:1",
            start_ms=0,
            end_ms=500,
            duration_ms=500,
        )
        baker.make(
            RecitationAyahTiming,
            track=track,
            ayah_key="1:2",
            start_ms=500,
            end_ms=900,
            duration_ms=400,
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("results", body)
        items = body["results"]
        self.assertEqual(1, len(items))
        timings = items[0]["ayahs_timings"]
        self.assertEqual(2, len(timings))
        # Verify shape and values
        self.assertEqual({"ayah_key": "1:1", "start_ms": 0, "end_ms": 500, "duration_ms": 500}, timings[0])
        self.assertEqual({"ayah_key": "1:2", "start_ms": 500, "end_ms": 900, "duration_ms": 400}, timings[1])

    def test_list_recitation_tracks_where_no_timings_should_return_empty_ayahs_timings(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
        )
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        self.assertEqual(1, len(items))
        self.assertEqual([], items[0]["ayahs_timings"])

    def test_list_recitation_tracks_where_timings_inserted_out_of_order_should_return_ordered_by_start_ms(self):
        # Forward-guard: verifies timings return ordered by start_ms after removal of the
        # Python sorted() call. Insertion order is intentionally scrambled so the test
        # would catch any future regression that drops the Prefetch ORDER BY.
        track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=3000,
            size_bytes=512,
        )
        baker.make(RecitationAyahTiming, track=track, ayah_key="1:3", start_ms=2000, end_ms=3000, duration_ms=1000)
        baker.make(RecitationAyahTiming, track=track, ayah_key="1:1", start_ms=0, end_ms=1000, duration_ms=1000)
        baker.make(RecitationAyahTiming, track=track, ayah_key="1:2", start_ms=1000, end_ms=2000, duration_ms=1000)
        self.authenticate_client(self.app)

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(200, response.status_code, response.content)
        timings = response.json()["results"][0]["ayahs_timings"]
        self.assertEqual(["1:1", "1:2", "1:3"], [t["ayah_key"] for t in timings])


class PublicRecitationPaginationTest(unittest.TestCase):
    def test_Input_where_page_size_exceeds_max_should_clamp_to_max(self):
        inp = PublicRecitationPagination.Input(page_size=200)
        self.assertEqual(PUBLIC_RECITATION_MAX_PAGE_SIZE, inp.page_size)

    def test_Input_where_page_size_within_max_should_preserve_value(self):
        inp = PublicRecitationPagination.Input(page_size=20)
        self.assertEqual(20, inp.page_size)

    def test_Input_where_page_size_equals_max_should_preserve_value(self):
        inp = PublicRecitationPagination.Input(page_size=PUBLIC_RECITATION_MAX_PAGE_SIZE)
        self.assertEqual(PUBLIC_RECITATION_MAX_PAGE_SIZE, inp.page_size)


class RecitationTracksPageSizeCapTest(BaseTestCase):
    def setUp(self):
        from django.core.cache import cache as django_cache

        super().setUp()
        django_cache.clear()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        self.user = User.objects.create_user(email="pagecap@example.com", name="Page Cap User")
        self.app = Application.objects.create(
            user=self.user,
            name="Page Cap App",
            client_type="confidential",
            authorization_grant_type="password",
        )
        for surah_number in range(1, 4):
            baker.make(
                RecitationSurahTrack,
                asset=self.asset,
                surah_number=surah_number,
                duration_ms=1000,
                size_bytes=512,
                audio_file=SimpleUploadedFile(f"s{surah_number}.mp3", b"dummy"),
            )

    def test_list_recitation_tracks_where_page_size_exceeds_max_should_be_clamped(self):
        # Fails on old code where @paginate had no cap.
        self.authenticate_client(self.app)

        response = self.client.get(f"/recitations/{self.asset.id}/?page_size=200")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        # All 3 tracks returned (< cap); effective page_size was clamped to PUBLIC_RECITATION_MAX_PAGE_SIZE.
        self.assertLessEqual(len(body["results"]), PUBLIC_RECITATION_MAX_PAGE_SIZE)

    def test_list_recitation_tracks_where_second_request_should_hit_cache(self):
        import json

        from django.core.cache import cache as django_cache

        self.authenticate_client(self.app)
        django_cache.clear()

        # First request populates cache.
        first = self.client.get(f"/recitations/{self.asset.id}/")
        self.assertEqual(200, first.status_code, first.content)

        # Pre-serialized response bytes must exist after first request.
        cached_bytes = django_cache.get(
            recitation_response_cache_key(self.asset.id, page=1, page_size=DEFAULT_PAGE_SIZE)
        )
        self.assertIsNotNone(cached_bytes)
        cached_data = json.loads(cached_bytes)
        self.assertEqual(3, len(cached_data["results"]))

        # Second request returns same data (served from cache).
        second = self.client.get(f"/recitations/{self.asset.id}/")
        self.assertEqual(200, second.status_code, second.content)
        self.assertEqual(first.json(), second.json())

    def test_list_recitation_tracks_where_meta_cache_warm_should_not_500_on_second_request(self):
        # Regression: asset_meta cache write must supply every key the cache-hit
        # read path looks up (name_ar), or the second request raises KeyError -> 500.
        from django.core.cache import cache as django_cache

        self.authenticate_client(self.app)
        django_cache.clear()

        first = self.client.get(f"/recitations/{self.asset.id}/")
        self.assertEqual(200, first.status_code, first.content)

        second = self.client.get(f"/recitations/{self.asset.id}/")
        self.assertEqual(200, second.status_code, second.content)
        self.assertEqual(first.json(), second.json())

    def test_list_recitation_tracks_where_both_caches_warm_should_make_no_db_query(self):
        # Fails on old code where get_asset_object always ran before the cache check.
        from unittest.mock import patch

        from django.core.cache import cache as django_cache

        self.authenticate_client(self.app)
        django_cache.clear()

        # Warm both caches via a real first request.
        first = self.client.get(f"/recitations/{self.asset.id}/")
        self.assertEqual(200, first.status_code, first.content)

        # Second request: response + meta caches are hot - repo must not be called.
        with patch("apps.content.api.public.recitation_track_list.RecitationRepository") as mock_repo_cls:
            second = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(200, second.status_code, second.content)
        mock_repo_cls.assert_not_called()


@override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
class RecitationTracksAccessControlTest(BaseTestCase):
    """Gating of the content endpoint behind API key + approved access request."""

    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            is_open_access=False,
            reciter=baker.make("content.Reciter", name="Test Reciter"),
            riwayah=baker.make("content.Riwayah", name="Test Riwayah"),
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            duration_ms=1000,
            size_bytes=512,
        )
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _authenticate_with_api_key(self, user: User) -> None:
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def _grant_access(self, user: User, asset: Asset) -> AssetAccess:
        req = baker.make(
            AssetAccessRequest,
            developer_user=user,
            asset=asset,
            status=AssetAccessRequest.StatusChoice.APPROVED,
        )
        return baker.make(AssetAccess, asset_access_request=req, user=user, asset=asset, expires_at=None)

    def test_open_access_asset_is_consumable_without_api_key(self):
        self.asset.is_open_access = True
        self.asset.save(update_fields=["is_open_access"])

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(200, response.status_code, response.content)

    def test_restricted_asset_without_api_key_returns_401(self):
        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])

    def test_restricted_asset_with_api_key_but_no_access_request_returns_403(self):
        self._authenticate_with_api_key(self.user)

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    def test_restricted_asset_with_rejected_access_request_returns_403(self):
        baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=self.asset,
            status=AssetAccessRequest.StatusChoice.REJECTED,
        )
        self._authenticate_with_api_key(self.user)

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    def test_restricted_asset_with_pending_access_request_returns_403(self):
        baker.make(
            AssetAccessRequest,
            developer_user=self.user,
            asset=self.asset,
            status=AssetAccessRequest.StatusChoice.PENDING,
        )
        self._authenticate_with_api_key(self.user)

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("access_denied", response.json()["error_name"])

    def test_restricted_asset_with_approved_access_returns_200(self):
        self._grant_access(self.user, self.asset)
        self._authenticate_with_api_key(self.user)

        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(response.json()["results"]))

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=False)
    def test_flag_off_restricted_asset_consumable_without_api_key(self):
        response = self.client.get(f"/recitations/{self.asset.id}/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(response.json()["results"]))
