from django.db import connection
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

    def test_create_where_name_already_exists_should_raise_already_exists(self):
        # Arrange
        service = MushafLayoutService()
        service.create(name_ar="المدني ٦٠٤", name_en="Madani 604", page_count=604)

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.create(name_ar="المدني ٦٠٤", name_en="Madani 604", page_count=604)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_already_exists")

    def test_create_where_both_names_blank_should_raise_name_required(self):
        # Arrange
        service = MushafLayoutService()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.create(name_ar="  ", name_en="", page_count=10)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_name_required")

    def test_update_where_name_en_changed_should_rewrite_the_physical_name_column(self):
        # Arrange
        # modeltranslation's manager transparently rewrites ORM lookups like
        # .values_list("name") to the active-language column, which would mask
        # a stale physical `name` column. Read it with a raw cursor instead so
        # the assertion actually inspects the DB row modeltranslation bypasses.
        service = MushafLayoutService()
        layout = baker.make(MushafLayout, name="E1", name_ar="", name_en="E1", page_count=10)

        # Act
        service.update(layout.pk, name_en="New Name")

        # Assert
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM content_mushaflayout WHERE id = %s", [layout.pk])
            physical_name = cursor.fetchone()[0]
        self.assertEqual(physical_name, "New Name")

    def test_update_where_rename_collides_with_existing_layout_should_raise_already_exists(self):
        # Arrange
        service = MushafLayoutService()
        baker.make(MushafLayout, name="Taken", name_ar="Taken", name_en="Taken", page_count=5)
        layout = baker.make(MushafLayout, name="Other", name_ar="Other", name_en="Other", page_count=6)

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.update(layout.pk, name_en="Taken")
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_already_exists")
