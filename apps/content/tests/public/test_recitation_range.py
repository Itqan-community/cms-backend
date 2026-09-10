from pathlib import Path
import subprocess
from unittest.mock import patch

import boto3
from django.core.cache import cache as django_cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.cache import recitation_range_cache_key
from apps.content.models import Asset, CategoryChoice, RecitationAyahTiming, RecitationSurahTrack, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


def _fake_ffmpeg(output_body: bytes):
    # Stand-in for the ffmpeg binary: writes bytes to the output path and exits 0.

    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(output_body)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    return fake_run


class RecitationRangeTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        django_cache.clear()
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
        self.folder = self.asset.recitation_folders.get(is_default=True)
        self.track = baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            folder=self.folder,
            surah_number=1,
            duration_ms=3000,
            size_bytes=512,
            audio_file=SimpleUploadedFile(name="test.mp3", content=b"dummy", content_type="audio/mpeg"),
        )
        for key, start, end in (("1:1", 0, 1000), ("1:2", 1000, 2000), ("1:3", 2000, 3000)):
            baker.make(
                RecitationAyahTiming,
                track=self.track,
                ayah_key=key,
                start_ms=start,
                end_ms=end,
                duration_ms=end - start,
            )
        self.user = User.objects.create_user(email="rangeuser@example.com", name="Range User")
        self.app = Application.objects.create(
            user=self.user,
            name="Range App",
            client_type="confidential",
            authorization_grant_type="password",
        )
        # The range service builds an R2 client against the configured endpoint,
        # which moto does not intercept; point it at a moto-intercepted client.
        self.s3 = boto3.client("s3", region_name="us-east-1")
        range_client_patcher = patch(
            "apps.content.api.public.recitation_range.RecitationRangeService._get_s3_client",
            return_value=self.s3,
        )
        range_client_patcher.start()
        self.addCleanup(range_client_patcher.stop)
        self.s3.put_object(Bucket=self.bucket_name, Key=f"media/{self.track.audio_file.name}", Body=b"source-mp3")
        ffmpeg_patcher = patch(
            "apps.content.services.recitation_range.subprocess.run", side_effect=_fake_ffmpeg(b"range-bytes")
        )
        ffmpeg_patcher.start()
        self.addCleanup(ffmpeg_patcher.stop)

    def _url(self, surah=1, query="from=1&to=2"):
        return f"/recitations/{self.asset.id}/{surah}/range/?{query}"

    def test_get_range_where_valid_should_return_combined_clip(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(self.asset.id, body["asset_id"])
        self.assertEqual(1, body["surah_number"])
        self.assertEqual(1, body["from_ayah"])
        self.assertEqual(2, body["to_ayah"])
        self.assertIn("range_001_002.mp3", body["audio_url"])
        self.assertEqual(2000, body["duration_ms"])
        self.assertEqual(["1:1", "1:2"], [t["ayah_key"] for t in body["ayahs_timings"]])
        self.assertEqual([0, 1000], [t["offset_ms"] for t in body["ayahs_timings"]])

    def test_get_range_where_repeated_should_serve_from_cache(self):
        # Arrange: warm the cache, then prove the second request needs no DB.
        self.authenticate_client(self.app)
        first = self.client.get(self._url())
        self.assertEqual(200, first.status_code, first.content)
        cache_key = recitation_range_cache_key(self.asset.id, 1, 1, 2, "__default__")
        self.assertIsNotNone(django_cache.get(cache_key))

        # Act: block the repository - a cache hit must not touch the DB.
        with patch("apps.content.api.public.recitation_range.RecitationRepository") as mock_repo_cls:
            mock_repo_cls.return_value.get_asset_object.side_effect = AssertionError("DB hit on cached range")
            second = self.client.get(self._url())

        # Assert
        self.assertEqual(200, second.status_code, second.content)
        self.assertEqual(first.content, second.content)

    def test_get_range_where_from_exceeds_to_should_return_422(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url(query="from=3&to=1"))

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_range_where_to_exceeds_surah_ayah_count_should_return_422(self):
        # Arrange: surah 1 has 7 ayahs; to=8 is outside the surah.
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url(query="from=1&to=8"))

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_range_where_timing_gap_should_return_422(self):
        # Arrange: delete the middle timing so 1-3 has a gap.
        RecitationAyahTiming.objects.filter(track=self.track, ayah_key="1:2").delete()
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url(query="from=1&to=3"))

        # Assert
        self.assertEqual(422, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_range_where_asset_missing_should_return_404(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/recitations/999999/1/range/?from=1&to=2")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_get_range_where_surah_track_missing_should_return_404(self):
        # Arrange: asset only has surah 1.
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url(surah=2, query="from=1&to=2"))

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_get_range_where_folder_unknown_should_return_404(self):
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get(self._url(query="from=1&to=2&folder=nope"))

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("folder_not_found", response.json()["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_range_where_private_and_anonymous_should_require_auth(self):
        # Arrange: private asset + enforced access, no credentials.
        self.asset.is_open_access = False
        self.asset.save(update_fields=["is_open_access", "updated_at"])
        django_cache.clear()

        # Act
        response = self.client.get(self._url())

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_get_range_where_open_flips_to_restricted_should_drop_cached_meta(self):
        # 1. Warm the range cache as an open-access asset (no credentials needed).
        warm = self.client.get(self._url())
        self.assertEqual(200, warm.status_code, warm.content)

        # 2. Flip to restricted: the post_save signal must bust the cached asset
        #    metadata, otherwise the warm path keeps trusting stale
        #    is_open_access=True and serves restricted audio anonymously (CWE-863).
        self.asset.is_open_access = False
        self.asset.save(update_fields=["is_open_access", "updated_at"])

        # 3. Anonymous request must be rebuilt from the DB and denied.
        response = self.client.get(self._url())
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])
