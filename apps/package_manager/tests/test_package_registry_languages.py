"""Language-aware resolution and content eligibility for the package registry.

Each AssetLanguage has its own version timeline (an Arabic ``1.0`` and an
Azerbaijani ``1.0`` are different versions), so resolution is scoped to one
language rendition: the requested one, or the asset's source language.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
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
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.package_manager.services.package_registry import PackageRegistryService, PackageRequest
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura


def _make_asset(publisher: Publisher, *, slug: str) -> Asset:
    return Asset.objects.create(
        status=StatusChoice.READY,
        name="Test Asset",
        slug=slug,
        publisher=publisher,
        category="translation",
        template=AssetTemplateChoice.AYAH,
        license="CC0",
        file_size="1 MB",
        format="csv",
        description="desc",
        language="ar",
    )


def _make_language(asset: Asset, code: str, *, status: str = StatusChoice.READY) -> AssetLanguage:
    return AssetLanguage.objects.create(asset=asset, language=code, is_source=False, status=status)


def _make_version(
    asset: Asset,
    *,
    name: str,
    language: AssetLanguage | None = None,
    with_file: bool = True,
) -> AssetVersion:
    version = baker.make(
        AssetVersion,
        asset=asset,
        asset_language=language or asset.get_or_create_source_language(),
        name=name,
        state=VersionStateChoice.PUBLISHED,
    )
    if with_file:
        version.file_url = SimpleUploadedFile(name=f"{asset.slug}-{name}.csv", content=b"sura,text\n")
        version.save()
    return version


class PackageRegistryLanguageResolutionTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.service = PackageRegistryService()

    def test_resolve_single_where_language_omitted_should_use_source_language_timeline(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        source_v1 = _make_version(asset, name="1.0")
        _make_version(asset, name="1.1", language=_make_language(asset, "az"))

        # Act
        result = self.service.resolve_single("tafsir", "^1.0.0")

        # Assert
        self.assertEqual(source_v1, result.asset_version)
        self.assertEqual("ar", result.asset_language.language)

    def test_resolve_single_where_language_given_should_use_that_language_timeline(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        _make_version(asset, name="1.5")
        azerbaijani = _make_language(asset, "az")
        az_v1 = _make_version(asset, name="1.0", language=azerbaijani)

        # Act
        result = self.service.resolve_single("tafsir", "^1.0.0", language="az")

        # Assert
        self.assertEqual(az_v1, result.asset_version)
        self.assertEqual("1.0.0", result.canonical_version)

    def test_resolve_single_where_same_name_in_two_languages_should_not_collide(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        source_v1 = _make_version(asset, name="1.0")
        _make_version(asset, name="1.0", language=_make_language(asset, "az"))

        # Act
        result = self.service.resolve_single("tafsir", "1.0.0")

        # Assert
        self.assertEqual(source_v1, result.asset_version)

    def test_resolve_single_where_language_unknown_should_return_404(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        _make_version(asset, name="1.0")

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("tafsir", "1.0.0", language="fr")

        # Assert
        self.assertEqual("language_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_single_where_language_is_draft_should_return_404(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        hidden = _make_language(asset, "az", status=StatusChoice.DRAFT)
        _make_version(asset, name="1.0", language=hidden)

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("tafsir", "1.0.0", language="az")

        # Assert
        self.assertEqual("language_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_resolve_single_where_duplicate_name_within_one_language_should_return_422(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        _make_version(asset, name="1.2")
        _make_version(asset, name="1.2.0")

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("tafsir", "^1.0.0")

        # Assert
        self.assertEqual("canonical_version_collision", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)

    def test_resolve_manifest_where_two_entries_name_two_languages_of_one_asset_should_resolve_both(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        source_v2 = _make_version(asset, name="2.0")
        az_v1 = _make_version(asset, name="1.0", language=_make_language(asset, "az"))

        # Act
        results = self.service.resolve_manifest(
            {
                "tafsir": PackageRequest(slug="tafsir", version="^2.0.0"),
                "tafsir-az": PackageRequest(slug="tafsir", version="^1.0.0", language="az"),
            }
        )

        # Assert
        by_name = {r.name: r for r in results}
        self.assertEqual(["tafsir", "tafsir-az"], [r.name for r in results])
        self.assertEqual(source_v2, by_name["tafsir"].asset_version)
        self.assertEqual(az_v1, by_name["tafsir-az"].asset_version)


class PackageRegistryContentEligibilityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.service = PackageRegistryService()
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=1)
        self.ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a1")

    def test_resolve_single_where_newest_version_has_no_content_should_skip_it(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        with_file = _make_version(asset, name="1.0")
        _make_version(asset, name="1.1", with_file=False)

        # Act
        result = self.service.resolve_single("tafsir", "^1.0.0")

        # Assert
        self.assertEqual(with_file, result.asset_version)

    def test_resolve_single_where_version_has_only_stored_changes_should_be_eligible(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        _make_version(asset, name="1.0")
        pruned = _make_version(asset, name="1.1", with_file=False)
        baker.make(
            AssetVersionChange, version=pruned, ayah=self.ayah, change_type=ChangeTypeChoice.MODIFIED, new_text="x"
        )

        # Act
        result = self.service.resolve_single("tafsir", "^1.0.0")

        # Assert
        self.assertEqual(pruned, result.asset_version)

    def test_resolve_single_where_version_has_only_entries_should_be_eligible(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        head = _make_version(asset, name="1.0", with_file=False)
        baker.make(AssetVersionEntry, version=head, ayah=self.ayah, text="x", order=1)

        # Act
        result = self.service.resolve_single("tafsir", "1.0.0")

        # Assert
        self.assertEqual(head, result.asset_version)

    def test_resolve_single_where_only_contentless_versions_should_return_422(self):
        # Arrange
        asset = _make_asset(self.publisher, slug="tafsir")
        _make_version(asset, name="1.0", with_file=False)

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.resolve_single("tafsir", "1.0.0")

        # Assert
        self.assertEqual("no_eligible_package_versions", ctx.exception.error_name)
        self.assertEqual(422, ctx.exception.status_code)
