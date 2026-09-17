from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class AssetTemplateImmutabilityTests(BaseTestCase):
    def test_save_where_template_changed_should_raise_itqan_error(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.template = AssetTemplateChoice.SURAH

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            reloaded.save()
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")

    def test_save_where_mushaf_layout_changed_should_raise_itqan_error(self):
        # Arrange
        first = baker.make(MushafLayout, name="Madani 604", page_count=604)
        second = baker.make(MushafLayout, name="Indo-Pak 611", page_count=611)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=first,
        )
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.mushaf_layout = second

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            reloaded.save()
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")

    def test_save_where_template_unchanged_should_save_other_fields(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.description = "updated"

        # Act
        reloaded.save()

        # Assert
        self.assertEqual(Asset.objects.get(pk=asset.pk).description, "updated")

    def test_save_where_asset_is_new_should_not_raise(self):
        # Arrange / Act
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)

        # Assert
        self.assertEqual(asset.template, AssetTemplateChoice.WORD)
