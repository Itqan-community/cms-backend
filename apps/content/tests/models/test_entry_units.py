from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import AssetTemplateChoice, AssetVersion, AssetVersionEntry, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura

# `baker.make(Asset)` alone leaves `category`/`template`/`reciter`/`riwayah` to
# whatever model_bakery's field-choice RNG lands on, which frequently violates
# `asset_template_required_for_text` or `asset_recitation_fields_consistency`
# (both pre-existing, unrelated to this test). Pinning a valid combination
# here keeps these tests about the *_exactly_one_unit constraint only.
_VALID_ASSET_KWARGS = {"asset__category": CategoryChoice.TRANSLATION, "asset__template": AssetTemplateChoice.SURAH}


class EntryUnitConstraintTests(BaseTestCase):
    # Task 3 creates the mixin; these tests bake inline so the mixin's own
    # first consumer is Task 5, after it has been reviewed.
    def test_entry_where_no_unit_is_set_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion, **_VALID_ASSET_KWARGS)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, text="x")

    def test_entry_where_two_units_are_set_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion, **_VALID_ASSET_KWARGS)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)
        ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="ayah 1")

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, sura=sura, ayah=ayah, text="x")

    def test_entry_where_only_sura_is_set_should_save(self):
        # Arrange
        version = baker.make(AssetVersion, **_VALID_ASSET_KWARGS)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)

        # Act
        entry = AssetVersionEntry.objects.create(version=version, sura=sura, text="x", order=sura.id)

        # Assert
        self.assertEqual(entry.sura_id, sura.id)
        self.assertIsNone(entry.ayah_id)

    def test_entry_where_only_page_no_is_set_should_save(self):
        # Arrange
        version = baker.make(AssetVersion, **_VALID_ASSET_KWARGS)

        # Act
        entry = AssetVersionEntry.objects.create(version=version, page_no=42, text="x", order=42)

        # Assert
        self.assertEqual(entry.page_no, 42)
        self.assertIsNone(entry.ayah_id)

    def test_entry_where_same_sura_twice_in_one_version_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion, **_VALID_ASSET_KWARGS)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)
        AssetVersionEntry.objects.create(version=version, sura=sura, text="a", order=sura.id)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, sura=sura, text="b", order=sura.id)
