"""GET /packages/: the catalog of installable assets and their languages."""

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    Qiraah,
    Reciter,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class PackageCatalogApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Publisher")

    def _asset(self, slug: str, **kwargs) -> Asset:
        defaults = {
            "name": slug.title(),
            "slug": slug,
            "publisher": self.publisher,
            "category": "tafsir",
            "template": AssetTemplateChoice.AYAH,
            "license": "CC0",
            "file_size": "1 MB",
            "format": "csv",
            "description": "desc",
            "language": "ar",
            "status": StatusChoice.READY,
        }
        return Asset.objects.create(**(defaults | kwargs))

    def _version(
        self, asset: Asset, name: str, *, language: AssetLanguage | None = None, with_file: bool = True
    ) -> AssetVersion:
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=language or asset.get_or_create_source_language(),
            name=name,
            state=VersionStateChoice.PUBLISHED,
        )
        if with_file:
            version.file_url = SimpleUploadedFile(name=f"{asset.slug}-{name}.csv", content=b"x")
            version.save()
        return version

    def _language(self, asset: Asset, code: str, *, status: str = StatusChoice.READY) -> AssetLanguage:
        return AssetLanguage.objects.create(asset=asset, language=code, is_source=False, status=status)

    def test_list_packages_where_asset_has_two_languages_should_list_latest_version_of_each(self):
        # Arrange
        asset = self._asset("tafsir")
        self._version(asset, "1.0")
        self._version(asset, "1.2")
        english = self._language(asset, "en")
        self._version(asset, "2.0", language=english)

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual(
            {
                "slug": "tafsir",
                "name": "Tafsir",
                "category": "tafsir",
                "is_open_access": True,
                "publisher_name": "Publisher",
                "languages": [
                    {"language": "ar", "is_source": True, "latest_version": "1.2.0"},
                    {"language": "en", "is_source": False, "latest_version": "2.0.0"},
                ],
            },
            body["results"][0],
        )

    def test_list_packages_where_assets_are_not_installable_should_leave_them_out(self):
        # Arrange
        self._version(self._asset("installable"), "1.0")
        self._version(self._asset("draft-asset", status=StatusChoice.DRAFT), "1.0")
        self._version(self._asset("tenant-only", restricted_for_tenant=True), "1.0")
        self._version(self._asset("no-content"), "1.0", with_file=False)
        hidden = self._asset("hidden-language", language="fr")
        source = hidden.get_or_create_source_language()
        source.status = StatusChoice.DRAFT
        source.save()
        self._version(hidden, "1.0", language=source)

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["installable"], [r["slug"] for r in response.json()["results"]])

    def test_list_packages_where_language_has_no_semver_version_should_omit_that_language(self):
        # Arrange
        asset = self._asset("tafsir")
        self._version(asset, "1.0")
        self._version(asset, "draft-2", language=self._language(asset, "en"))

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["ar"], [lang["language"] for lang in response.json()["results"][0]["languages"]])

    def test_list_packages_where_open_access_filter_given_should_list_only_open_assets(self):
        # Arrange
        self._version(self._asset("open"), "1.0")
        self._version(self._asset("gated", is_open_access=False), "1.0")

        # Act
        response = self.client.get("/packages/?open_access=true")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["open"], [r["slug"] for r in response.json()["results"]])

    def test_list_packages_where_newest_version_is_prerelease_should_report_latest_stable(self):
        # Arrange
        asset = self._asset("tafsir")
        self._version(asset, "1.0")
        self._version(asset, "2.0.0-rc.1")

        # Act
        response = self.client.get("/packages/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("1.0.0", response.json()["results"][0]["languages"][0]["latest_version"])

    def test_list_packages_where_search_given_should_match_name_slug_and_publisher(self):
        # Arrange
        self._version(self._asset("tafsir-jalalayn", name="Jalalayn"), "1.0")
        self._version(self._asset("mushaf-madinah", name="Madinah Mushaf"), "1.0")
        other_publisher = baker.make(Publisher, name="King Fahd Complex")
        self._version(self._asset("font-hafs", name="Hafs Font", publisher=other_publisher), "1.0")

        # Act
        by_name = self.client.get("/packages/", {"search": "jalal"})
        by_slug = self.client.get("/packages/", {"search": "mushaf-mad"})
        by_publisher = self.client.get("/packages/", {"search": "fahd"})

        # Assert
        self.assertEqual(["tafsir-jalalayn"], [r["slug"] for r in by_name.json()["results"]])
        self.assertEqual(["mushaf-madinah"], [r["slug"] for r in by_slug.json()["results"]])
        self.assertEqual(["font-hafs"], [r["slug"] for r in by_publisher.json()["results"]])

    def test_list_packages_where_category_given_should_list_only_that_category(self):
        # Arrange
        self._version(self._asset("tafsir-a", category="tafsir"), "1.0")
        self._version(self._asset("mushaf-a", category="mushaf", template=None), "1.0")

        # Act
        response = self.client.get("/packages/", {"category": "mushaf"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["mushaf-a"], [r["slug"] for r in response.json()["results"]])

    def test_list_packages_where_category_is_unknown_should_return_400(self):
        # Arrange
        self._version(self._asset("tafsir-a"), "1.0")

        # Act
        response = self.client.get("/packages/", {"category": "not-a-category"})

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_list_packages_where_asset_is_recitation_should_leave_it_out(self):
        # Arrange
        self._version(self._asset("tafsir-a"), "1.0")
        recitation = self._asset(
            "recitation-a",
            category="recitation",
            template=None,
            reciter=baker.make(Reciter),
            qiraah=baker.make(Qiraah),
        )
        self._version(recitation, "1.0")

        # Act
        all_assets = self.client.get("/packages/")
        recitations = self.client.get("/packages/", {"category": "recitation"})

        # Assert
        self.assertEqual(["tafsir-a"], [r["slug"] for r in all_assets.json()["results"]])
        self.assertEqual(200, recitations.status_code, recitations.content)
        self.assertEqual([], recitations.json()["results"])
