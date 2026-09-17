from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.tests.base import BaseTestCase


class AssetTemplateConstraintTests(BaseTestCase):
    def test_asset_where_translation_has_no_template_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(Asset, category=CategoryChoice.TRANSLATION, template=None)

    def test_asset_where_font_has_a_template_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(Asset, category=CategoryChoice.FONT, template=AssetTemplateChoice.AYAH)

    def test_asset_where_page_template_has_no_layout_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(
                Asset,
                category=CategoryChoice.TRANSLATION,
                template=AssetTemplateChoice.PAGE,
                mushaf_layout=None,
            )

    def test_asset_where_ayah_template_has_a_layout_should_raise_integrity_error(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(
                Asset,
                category=CategoryChoice.TRANSLATION,
                template=AssetTemplateChoice.AYAH,
                mushaf_layout=layout,
            )

    def test_asset_where_page_template_has_a_layout_should_save(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Assert
        self.assertEqual(asset.mushaf_layout_id, layout.id)
        self.assertEqual(asset.template, AssetTemplateChoice.PAGE)
