from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.mushaf_layout import MushafLayoutService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class MushafLayoutServiceTests(BaseTestCase):
    def test_create_where_valid_should_persist_the_layout(self):
        # Arrange
        service = MushafLayoutService()

        # Act
        layout = service.create(name_ar="المدني ٦٠٤", name_en="Madani 604", page_count=604)

        # Assert
        self.assertEqual(MushafLayout.objects.get(pk=layout.pk).page_count, 604)

    def test_delete_where_an_asset_uses_the_layout_should_raise_in_use(self):
        # Arrange
        service = MushafLayoutService()
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.delete(layout.pk)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_in_use")

    def test_delete_where_unused_should_remove_the_layout(self):
        # Arrange
        service = MushafLayoutService()
        layout = baker.make(MushafLayout, name="Unused", page_count=10)

        # Act
        service.delete(layout.pk)

        # Assert
        self.assertFalse(MushafLayout.objects.filter(pk=layout.pk).exists())

    def test_update_where_layout_missing_should_raise_not_found(self):
        # Arrange
        service = MushafLayoutService()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.update(999999, page_count=5)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_not_found")
