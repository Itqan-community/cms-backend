from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class UnitSpecTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_total_where_template_is_surah_should_return_114(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert — 2 suras baked by bake_quran, not the canonical 114
        self.assertEqual(total, 2)

    def test_total_where_template_is_ayah_should_return_6236(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert — 3 ayahs baked by bake_quran, not the canonical 6236
        self.assertEqual(total, 3)

    def test_total_where_template_is_page_should_return_layout_page_count(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert
        self.assertEqual(total, 604)

    def test_units_where_template_is_surah_should_label_with_number_and_name(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)

        # Act
        first = unit_spec_for(asset).units(asset)[0]

        # Assert
        self.assertEqual(first.unit_id, 1)
        self.assertEqual(first.label, "1. Al-Fatiha")
        self.assertEqual(first.sura, 1)
        self.assertIsNone(first.aya)

    def test_units_where_template_is_page_should_label_with_page_number(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Small", page_count=3)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        rows = unit_spec_for(asset).units(asset)

        # Assert
        self.assertEqual([row.unit_id for row in rows], [1, 2, 3])
        self.assertEqual(rows[0].label, "Page 1")
        self.assertEqual(rows[0].reference_text, "")

    def test_units_where_word_template_filtered_by_sura_should_only_return_that_sura(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)

        # Act
        rows = unit_spec_for(asset).units(asset, sura=1)

        # Assert
        self.assertTrue(rows)
        self.assertTrue(all(row.sura == 1 for row in rows))

    def test_unit_spec_for_where_asset_has_no_template_should_raise(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.FONT, template=None)

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            unit_spec_for(asset)
        self.assertEqual(ctx.exception.error_name, "asset_template_missing")

    def test_units_page_where_offset_given_should_return_that_window(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=1, limit=5)

        # Assert — 3 ayahs baked; offset 1 limit 5 yields ids 2 and 3
        self.assertEqual(total, 3)
        self.assertEqual([row.unit_id for row in rows], [2, 3])

    def test_units_page_where_page_template_should_window_the_range(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=600, limit=10)

        # Assert
        self.assertEqual(total, 604)
        self.assertEqual([row.unit_id for row in rows], [601, 602, 603, 604])
