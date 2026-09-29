import importlib

from django.apps import apps as django_apps

from apps.content.models import MushafLayout
from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
seed = importlib.import_module("apps.content.migrations.0068_seed_mushaf_layouts")


class SeedMushafLayoutsTests(BaseTestCase):
    def test_seed_mushaf_layouts_where_migrated_should_provide_madinah_and_shamarly(self):
        # Arrange / Act: the test database is built by running the migrations.
        layouts = {layout.name_en: layout for layout in MushafLayout.objects.all()}

        # Assert
        self.assertEqual(layouts["Madinah Mushaf"].page_count, 604)
        self.assertEqual(layouts["Madinah Mushaf"].name_ar, "مصحف المدينة")
        self.assertEqual(layouts["Shamarly Mushaf"].page_count, 522)
        self.assertEqual(layouts["Shamarly Mushaf"].name_ar, "مصحف الشمرلي")

    def test_seed_mushaf_layouts_where_run_again_should_not_duplicate(self):
        # Arrange
        before = MushafLayout.objects.count()

        # Act
        seed.seed_mushaf_layouts(django_apps, None)

        # Assert
        self.assertEqual(MushafLayout.objects.count(), before)

    def test_seed_mushaf_layouts_where_layout_exists_should_keep_its_values(self):
        # Arrange
        MushafLayout.objects.filter(name_en="Madinah Mushaf").update(page_count=600)

        # Act
        seed.seed_mushaf_layouts(django_apps, None)

        # Assert
        self.assertEqual(MushafLayout.objects.get(name_en="Madinah Mushaf").page_count, 600)
