import importlib

from django.apps import apps as django_apps
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.package_manager.services.package_registry import PackageRegistryService
from apps.publishers.models import MemberLanguage

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0005_language_codes_and_mushaf_font_numbers")
# Runs after 0005 on deploy: publishes each mushaf / font language's newest version.
publish_migration = importlib.import_module("apps.content.migrations.0007_publish_newest_mushaf_and_font_versions")


class NumberMushafFontVersionsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.mushaf = baker.make(
            Asset, category=CategoryChoice.MUSHAF, status=StatusChoice.READY, language="ar", slug="madinah-1441"
        )
        self.font = baker.make(
            Asset, category=CategoryChoice.FONT, status=StatusChoice.READY, language="ar", slug="uthmanic-hafs"
        )

    def test_number_mushaf_font_versions_where_name_is_title_should_issue_1_0_and_keep_title_as_label(self):
        # Arrange
        mushaf_version = baker.make(AssetVersion, asset=self.mushaf, name="مصحف المدينة النبوية حفص 1441 هـ")
        font_version = baker.make(AssetVersion, asset=self.font, name="Unicode Uthmanic Font (Hafs Narration)")

        # Act
        migration.number_mushaf_font_versions(django_apps, None)

        # Assert
        mushaf_version.refresh_from_db()
        font_version.refresh_from_db()
        self.assertEqual("1.0", mushaf_version.name)
        self.assertEqual("مصحف المدينة النبوية حفص 1441 هـ", mushaf_version.label_ar)
        self.assertFalse(mushaf_version.label_en)
        self.assertEqual("1.0", font_version.name)
        self.assertEqual("Unicode Uthmanic Font (Hafs Narration)", font_version.label_en)
        self.assertFalse(font_version.label_ar)

    def test_number_mushaf_font_versions_where_several_unnumbered_should_number_in_creation_order(self):
        # Arrange
        first = baker.make(AssetVersion, asset=self.mushaf, name="v1")
        second = baker.make(AssetVersion, asset=self.mushaf, name="second printing")

        # Act
        migration.number_mushaf_font_versions(django_apps, None)

        # Assert
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual("1.0", first.name)
        self.assertEqual("v1", first.label_en)
        self.assertEqual("1.1", second.name)

    def test_number_mushaf_font_versions_where_sequence_has_numbers_should_continue_after_highest(self):
        # Arrange
        numbered = baker.make(AssetVersion, asset=self.font, name="2.3")
        unnumbered = baker.make(AssetVersion, asset=self.font, name="Later upload")

        # Act
        migration.number_mushaf_font_versions(django_apps, None)

        # Assert
        numbered.refresh_from_db()
        unnumbered.refresh_from_db()
        self.assertEqual("2.3", numbered.name)
        self.assertEqual("2.4", unnumbered.name)

    def test_number_mushaf_font_versions_where_label_already_set_should_keep_it(self):
        # Arrange
        version = baker.make(AssetVersion, asset=self.font, name="Old title", label_en="Existing label")

        # Act
        migration.number_mushaf_font_versions(django_apps, None)

        # Assert
        version.refresh_from_db()
        self.assertEqual("1.0", version.name)
        self.assertEqual("Existing label", version.label_en)

    def test_number_mushaf_font_versions_where_other_category_or_draft_should_leave_them(self):
        # Arrange
        tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            language="ar",
            template=AssetTemplateChoice.AYAH,
        )
        tafsir_version = baker.make(AssetVersion, asset=tafsir, name="Free text")
        draft = baker.make(AssetVersion, asset=self.mushaf, name="", state=VersionStateChoice.DRAFT)

        # Act
        migration.number_mushaf_font_versions(django_apps, None)

        # Assert
        tafsir_version.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual("Free text", tafsir_version.name)
        self.assertEqual("", draft.name)

    def test_number_mushaf_font_versions_where_version_has_file_should_become_installable(self):
        # Arrange
        baker.make(AssetVersion, asset=self.mushaf, name="مصحف المدينة", file_url="uploads/mushaf.zip")
        self.assertEqual([], PackageRegistryService().catalog_languages(self.mushaf))

        # Act
        migration.number_mushaf_font_versions(django_apps, None)
        publish_migration.publish_newest_versions(django_apps, None)

        # Assert
        languages = PackageRegistryService().catalog_languages(self.mushaf)
        self.assertEqual(["ar"], [language.language for language in languages])
        self.assertEqual("1.0.0", languages[0].latest_version)


class NormalizeLanguageCodesTests(BaseTestCase):
    def _mushaf(self, language: str) -> Asset:
        return baker.make(Asset, category=CategoryChoice.MUSHAF, status=StatusChoice.READY, language=language)

    def test_normalize_language_codes_where_language_is_a_name_should_store_the_code(self):
        # Arrange
        asset = self._mushaf("Arabic")
        rendition = baker.make(
            AssetLanguage, asset=asset, language="Arabic", is_source=True, status=StatusChoice.READY
        )
        english = baker.make(AssetLanguage, asset=asset, language="English", status=StatusChoice.READY)

        # Act
        migration.normalize_language_codes(django_apps, None)

        # Assert
        asset.refresh_from_db()
        rendition.refresh_from_db()
        english.refresh_from_db()
        self.assertEqual("ar", asset.language)
        self.assertEqual("ar", rendition.language)
        self.assertEqual("en", english.language)

    def test_normalize_language_codes_where_native_or_cased_name_should_store_the_code(self):
        # Arrange
        native = self._mushaf("العربية")
        cased = self._mushaf(" FRENCH ")

        # Act
        migration.normalize_language_codes(django_apps, None)

        # Assert
        native.refresh_from_db()
        cased.refresh_from_db()
        self.assertEqual("ar", native.language)
        self.assertEqual("fr", cased.language)

    def test_normalize_language_codes_where_value_unknown_should_leave_it(self):
        # Arrange
        asset = self._mushaf("Klingon")

        # Act
        migration.normalize_language_codes(django_apps, None)

        # Assert
        asset.refresh_from_db()
        self.assertEqual("Klingon", asset.language)

    def test_normalize_language_codes_where_code_already_used_by_asset_should_skip_rename(self):
        # Arrange
        asset = self._mushaf("ar")
        baker.make(AssetLanguage, asset=asset, language="ar", is_source=True)
        duplicate = baker.make(AssetLanguage, asset=asset, language="Arabic")

        # Act
        migration.normalize_language_codes(django_apps, None)

        # Assert
        duplicate.refresh_from_db()
        self.assertEqual("Arabic", duplicate.language)
        self.assertEqual(1, AssetLanguage.objects.filter(asset=asset, language="ar").count())

    def test_normalize_language_codes_where_member_language_is_a_name_should_store_the_code(self):
        # Arrange
        member_language = baker.make(MemberLanguage, language="French")

        # Act
        migration.normalize_language_codes(django_apps, None)

        # Assert
        member_language.refresh_from_db()
        self.assertEqual("fr", member_language.language)

    def test_normalize_language_codes_where_catalog_lists_asset_should_report_the_code(self):
        # Arrange
        asset = self._mushaf("Arabic")
        baker.make(AssetVersion, asset=asset, name="1.0", file_url="uploads/mushaf.zip")

        # Act
        migration.normalize_language_codes(django_apps, None)
        publish_migration.publish_newest_versions(django_apps, None)

        # Assert
        languages = PackageRegistryService().catalog_languages(asset)
        self.assertEqual(["ar"], [language.language for language in languages])
