"""Public package API: language-aware requests, absolute download URLs, and
generating a version's file on its first download."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    ChangeTypeChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura


class PackageApiTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=2)
        self.ayah1 = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a1")
        self.ayah2 = baker.make(Ayah, id=2, sura=sura, number_in_sura=2, text="a2")
        self.asset = Asset.objects.create(
            status=StatusChoice.READY,
            name="Tafsir",
            slug="tafsir",
            publisher=self.publisher,
            category="tafsir",
            template=AssetTemplateChoice.AYAH,
            license="CC0",
            file_size="1 MB",
            format="csv",
            description="desc",
            language="ar",
        )

    def _language(self, code: str, *, status: str = StatusChoice.READY) -> AssetLanguage:
        return AssetLanguage.objects.create(asset=self.asset, language=code, is_source=False, status=status)

    def _version(self, name: str, *, language: AssetLanguage | None = None, with_file: bool = True) -> AssetVersion:
        version = baker.make(
            AssetVersion,
            asset=self.asset,
            asset_language=language or self.asset.get_or_create_source_language(),
            name=name,
            state=VersionStateChoice.PUBLISHED,
        )
        if with_file:
            version.file_url = SimpleUploadedFile(name=f"tafsir-{name}.csv", content=b"surah,ayah,text\n")
            version.save()
        return version

    def _pruned_version(self, name: str, *, language: AssetLanguage | None = None) -> AssetVersion:
        """A superseded commit: no file, no entries, only its stored changes
        on top of an earlier snapshot."""
        anchor = self._version("0.9", language=language, with_file=False)
        baker.make(AssetVersionEntry, version=anchor, ayah=self.ayah1, text="first", order=1)
        pruned = self._version(name, language=language, with_file=False)
        baker.make(
            AssetVersionChange,
            version=pruned,
            ayah=self.ayah2,
            change_type=ChangeTypeChoice.ADDED,
            new_text="second",
            order=2,
        )
        return pruned


class PackageLanguageApiTests(PackageApiTestCase):
    def test_resolve_package_manifest_where_entries_name_two_languages_should_return_both(self):
        # Arrange
        source = self._version("2.0")
        azerbaijani = self._version("1.0", language=self._language("az"))

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={
                "assets": {
                    "tafsir": "^2.0.0",
                    "tafsir-az": {"asset": "tafsir", "language": "az", "version": "^1.0.0"},
                }
            },
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        by_name = {r["name"]: r for r in response.json()["results"]}
        self.assertEqual(source.pk, by_name["tafsir"]["asset_version_id"])
        self.assertEqual("ar", by_name["tafsir"]["language"])
        self.assertEqual(azerbaijani.pk, by_name["tafsir-az"]["asset_version_id"])
        self.assertEqual("az", by_name["tafsir-az"]["language"])
        self.assertEqual("tafsir", by_name["tafsir-az"]["slug"])

    def test_resolve_package_manifest_where_entry_object_omits_asset_should_use_entry_name(self):
        # Arrange
        version = self._version("1.0", language=self._language("az"))

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/",
            data={"assets": {"tafsir": {"language": "az", "version": "1.0"}}},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(version.pk, response.json()["results"][0]["asset_version_id"])

    def test_resolve_package_single_where_language_query_given_should_resolve_that_language(self):
        # Arrange
        self._version("2.0")
        azerbaijani = self._version("1.0", language=self._language("az"))

        # Act
        response = self.client.get("/packages/resolve/tafsir/?version=^1.0.0&language=az")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(azerbaijani.pk, response.json()["result"]["asset_version_id"])
        self.assertEqual("az", response.json()["result"]["language"])

    def test_resolve_package_single_where_language_is_draft_should_return_404(self):
        # Arrange
        self._version("1.0", language=self._language("az", status=StatusChoice.DRAFT))

        # Act
        response = self.client.get("/packages/resolve/tafsir/?version=1.0&language=az")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("language_not_found", response.json()["error_name"])


class PackageAssetStatusApiTests(PackageApiTestCase):
    def test_resolve_package_single_where_asset_is_draft_should_return_404(self):
        # Arrange
        self._version("1.0")
        self.asset.status = StatusChoice.DRAFT
        self.asset.save()

        # Act
        response = self.client.get("/packages/resolve/tafsir/?version=1.0")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_resolve_package_manifest_where_asset_is_draft_should_return_404(self):
        # Arrange
        self._version("1.0")
        self.asset.status = StatusChoice.DRAFT
        self.asset.save()

        # Act
        response = self.client.post(
            "/packages/resolve/manifest/", data={"assets": {"tafsir": "1.0"}}, content_type="application/json"
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_download_package_file_where_asset_is_draft_should_return_404(self):
        # Arrange
        version = self._version("1.0")
        self.asset.status = StatusChoice.DRAFT
        self.asset.save()

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])


class PackageDownloadUrlApiTests(PackageApiTestCase):
    def test_resolve_package_single_where_version_has_file_should_return_absolute_file_url(self):
        # Arrange
        version = self._version("1.0")

        # Act
        response = self.client.get("/packages/resolve/tafsir/?version=1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(f"http://testserver{version.file_url.url}", response.json()["result"]["download_url"])

    def test_resolve_package_single_where_version_has_no_file_should_return_download_endpoint(self):
        # Arrange
        version = self._pruned_version("1.0")

        # Act
        response = self.client.get("/packages/resolve/tafsir/?version=1.0")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            f"http://testserver/packages/download/{version.pk}/tafsir-ar-1.0.csv/",
            response.json()["result"]["download_url"],
        )


class DownloadPackageFileTests(PackageApiTestCase):
    def test_download_package_file_where_version_has_file_should_redirect_to_it(self):
        # Arrange
        version = self._version("1.0")

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        self.assertEqual(version.file_url.url, response["Location"])

    def test_download_package_file_where_version_has_no_file_should_generate_and_save_it(self):
        # Arrange
        version = self._pruned_version("1.0")

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        version.refresh_from_db()
        self.assertTrue(version.file_url)
        self.assertEqual(version.file_url.url, response["Location"])
        with version.file_url.open("rb") as f:
            self.assertEqual(b"surah,ayah,text\r\n1,1,first\r\n1,2,second\r\n", f.read())
        self.assertEqual(len(b"surah,ayah,text\r\n1,1,first\r\n1,2,second\r\n"), version.size_bytes)

    def test_download_package_file_where_called_twice_should_generate_once(self):
        # Arrange
        version = self._pruned_version("1.0")
        self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")
        version.refresh_from_db()
        first_name = version.file_url.name

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        version.refresh_from_db()
        self.assertEqual(first_name, version.file_url.name)

    def test_download_package_file_where_version_has_no_content_should_return_404(self):
        # Arrange
        version = self._version("1.0", with_file=False)

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_download_package_file_where_language_is_draft_should_return_404(self):
        # Arrange
        version = self._version("1.0", language=self._language("az", status=StatusChoice.DRAFT))

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-az-1.0.csv/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    @override_settings(ENFORCE_ASSET_ACCESS_ON_PUBLIC_API=True)
    def test_download_package_file_where_restricted_and_anonymous_should_return_401(self):
        # Arrange
        self.asset.is_open_access = False
        self.asset.save()
        version = self._pruned_version("1.0")

        # Act
        response = self.client.get(f"/packages/download/{version.pk}/tafsir-ar-1.0.csv/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_required", response.json()["error_name"])
        version.refresh_from_db()
        self.assertFalse(version.file_url)
