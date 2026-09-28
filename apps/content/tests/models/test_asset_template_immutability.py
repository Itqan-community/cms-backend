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

    def test_from_db_where_only_defers_template_should_not_recurse(self):
        # Arrange
        baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        assets = list(Asset.objects.only("id", "name"))

        # Assert
        self.assertEqual(len(assets), 1)

    def test_from_db_where_defer_excludes_template_should_not_recurse(self):
        # Arrange
        baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        assets = list(Asset.objects.defer("template"))

        # Assert
        self.assertEqual(len(assets), 1)

    def test_save_where_deferred_instance_edits_unrelated_field_should_not_raise(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        deferred = Asset.objects.only("id", "name", "description").get(pk=asset.pk)
        deferred.description = "touched via deferred instance"

        # Act
        deferred.save(update_fields=["description"])

        # Assert
        self.assertEqual(Asset.objects.get(pk=asset.pk).description, "touched via deferred instance")

    def test_save_where_refreshed_after_external_update_should_not_raise(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        instance = Asset.objects.get(pk=asset.pk)
        Asset.objects.filter(pk=asset.pk).update(template=AssetTemplateChoice.SURAH)
        instance.refresh_from_db()
        instance.description = "touched after refresh"

        # Act
        instance.save()

        # Assert
        self.assertEqual(Asset.objects.get(pk=asset.pk).description, "touched after refresh")
