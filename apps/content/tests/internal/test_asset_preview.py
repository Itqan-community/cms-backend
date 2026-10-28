import io
import shutil
from unittest.mock import patch
import zipfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetVersion,
    CategoryChoice,
    RecitationFolder,
    RecitationSurahTrack,
    StatusChoice,
)
from apps.content.services.asset_preview import AssetPreviewService
from apps.content.tests.publishing import publish
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase

CDN = "https://storage.example.com"


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@override_settings(CLOUDFLARE_R2_PUBLIC_BASE_URL=CDN)
class RecitationPreviewTests(BaseTestCase):
    def _recitation(self, **kwargs) -> Asset:
        return baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            reciter=baker.make("content.Reciter"),
            riwayah=baker.make("content.Riwayah"),
            **{"status": StatusChoice.READY, "restricted_for_tenant": False, "is_open_access": True, **kwargs},
        )

    def _track(self, asset: Asset, surah: int, folder: RecitationFolder | None = None) -> RecitationSurahTrack:
        return baker.make(
            RecitationSurahTrack,
            asset=asset,
            folder=folder or asset.recitation_folders.get(is_default=True),
            surah_number=surah,
            audio_file=SimpleUploadedFile(f"{surah:03}.mp3", b"audio"),
            duration_ms=1000 * surah,
            size_bytes=5,
        )

    def test_recitation_preview_where_open_asset_has_four_tracks_should_return_first_three_on_cdn(self):
        # Arrange
        asset = self._recitation()
        for surah in (4, 1, 3, 2):
            self._track(asset, surah)

        # Act — anonymous: no access grant is needed
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        tracks = response.json()["tracks"]
        self.assertEqual([t["surah_number"] for t in tracks], [1, 2, 3])
        self.assertEqual(tracks[0]["surah_name_en"], "Al-Fatihah")
        self.assertEqual(tracks[0]["duration_ms"], 1000)
        self.assertTrue(all(t["audio_url"].startswith(f"{CDN}/media/") for t in tracks), tracks)

    def test_recitation_preview_where_asset_restricted_should_return_signed_urls_not_cdn(self):
        # Arrange
        asset = self._recitation(is_open_access=False)
        self._track(asset, 1)

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["tracks"][0]["audio_url"].startswith(CDN))

    def test_recitation_preview_where_tracks_only_in_other_folder_should_return_404(self):
        # Arrange
        asset = self._recitation()
        self._track(asset, 1, folder=baker.make(RecitationFolder, asset=asset, name="Echo"))

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "recitation_preview_unavailable")

    def test_recitation_preview_where_default_folder_hidden_should_return_404(self):
        # Arrange
        asset = self._recitation()
        self._track(asset, 1)
        asset.recitation_folders.filter(is_default=True).update(is_visible=False)

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "recitation_preview_unavailable")

    def test_recitation_preview_where_asset_draft_should_return_404(self):
        # Arrange
        asset = self._recitation(status=StatusChoice.DRAFT)
        self._track(asset, 1)

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "recitation_preview_unavailable")

    def test_recitation_preview_where_asset_restricted_for_tenant_should_return_404(self):
        # Arrange
        asset = self._recitation(restricted_for_tenant=True)
        self._track(asset, 1)

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/recitation-preview/")

        # Assert
        self.assertEqual(response.status_code, 404, response.content)


@override_settings(CLOUDFLARE_R2_PUBLIC_BASE_URL=CDN)
class FontPreviewTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.bake_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.FONT,
            status=StatusChoice.READY,
            language="ar",
            restricted_for_tenant=False,
            is_open_access=True,
        )
        self.url = f"/cms-api/assets/{self.asset.id}/font-preview/"
        self.versions: list[AssetVersion] = []

    def tearDown(self):
        # Extracted fonts land in the real MEDIA_ROOT: remove this test's.
        for version in self.versions:
            shutil.rmtree(version.file_url.storage.path(f"previews/fonts/{version.pk}"), ignore_errors=True)
        super().tearDown()

    def _publish(self, name: str, content: bytes) -> AssetVersion:
        rendition = self.asset.get_or_create_source_language()
        rendition.status = StatusChoice.READY
        rendition.save()
        version = publish(
            baker.make(
                AssetVersion,
                asset=self.asset,
                asset_language=rendition,
                file_url=SimpleUploadedFile(name, content),
            )
        )
        self.versions.append(version)
        return version

    def test_font_preview_where_version_is_a_font_file_should_return_it_with_fatiha_sample(self):
        # Arrange
        version = self._publish("almadinah.otf", b"OTTO-font")

        # Act — anonymous: no access grant is needed
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["font_url"], f"{CDN}/media/{version.file_url.name}")
        self.assertEqual(body["format"], "opentype")
        self.assertEqual(body["file_name"], version.file_url.name.rsplit("/", 1)[-1])
        self.assertEqual(body["sample"], [{"ayah": 1, "text": "ayah 1"}, {"ayah": 2, "text": "ayah 2"}])

    def test_font_preview_where_version_is_zip_should_extract_preferred_font_once(self):
        # Arrange
        version = self._publish(
            "uthmanic.zip",
            _zip(
                {
                    "data/hafs.csv": b"csv",
                    "__MACOSX/font/._hafs.ttf": b"meta",
                    "font/hafs.ttf": b"ttf-bytes",
                    "font/hafs.woff2": b"woff2-bytes",
                }
            ),
        )
        storage = version.file_url.storage

        # Act
        first = self.client.get(self.url)
        with patch.object(AssetPreviewService, AssetPreviewService._extract.__name__) as extract:
            second = self.client.get(self.url)

        # Assert
        self.assertEqual(first.status_code, 200, first.content)
        body = first.json()
        self.assertEqual(body["format"], "woff2")
        self.assertEqual(body["file_name"], "hafs.woff2")
        name = body["font_url"].removeprefix(f"{CDN}/media/")
        self.assertTrue(name.startswith(f"previews/fonts/{version.pk}/"), name)
        with storage.open(name) as extracted:
            self.assertEqual(extracted.read(), b"woff2-bytes")
        self.assertEqual(second.json(), body)
        extract.assert_not_called()

    def test_font_preview_where_name_cache_evicted_should_reuse_extracted_file(self):
        # Arrange
        self._publish("uthmanic.zip", _zip({"font/hafs.ttf": b"ttf-bytes"}))
        first = self.client.get(self.url).json()
        cache.clear()

        # Act
        with patch.object(AssetPreviewService, AssetPreviewService._extract.__name__) as extract:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.json(), first)
        extract.assert_not_called()

    def test_font_preview_where_asset_restricted_should_return_signed_url_not_cdn(self):
        # Arrange
        Asset.objects.filter(pk=self.asset.pk).update(is_open_access=False)
        self._publish("uthmanic.zip", _zip({"font/hafs.ttf": b"ttf-bytes"}))

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["font_url"].startswith(CDN))
        self.assertEqual(response.json()["format"], "truetype")

    def test_font_preview_where_zip_has_no_font_should_return_404(self):
        # Arrange
        self._publish("data.zip", _zip({"data/hafs.csv": b"csv"}))

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "font_preview_unavailable")

    def test_font_preview_where_upload_is_not_a_zip_should_return_404(self):
        # Arrange
        self._publish("setup.rar", b"Rar!not-a-zip")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "font_preview_unavailable")

    def test_font_preview_where_no_published_version_should_return_404(self):
        # Arrange — a language with no published version

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "font_preview_unavailable")

    def test_font_preview_where_language_hidden_should_return_404(self):
        # Arrange
        self._publish("almadinah.otf", b"OTTO-font")
        self.asset.languages.update(status=StatusChoice.DRAFT)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(response.status_code, 404, response.content)
        self.assertEqual(response.json()["error_name"], "font_preview_unavailable")
