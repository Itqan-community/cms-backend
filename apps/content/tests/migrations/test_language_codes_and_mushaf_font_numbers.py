import importlib

from django.apps import apps as django_apps
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase
from apps.package_manager.services.package_registry import PackageRegistryService

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0005_language_codes_and_mushaf_font_numbers")


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

        # Assert
        languages = PackageRegistryService().catalog_languages(self.mushaf)
        self.assertEqual(["ar"], [language.language for language in languages])
        self.assertEqual("1.0.0", languages[0].latest_version)

