from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.content.models import AssetTemplateChoice, MushafLayout
from apps.core.tests.base import BaseTestCase


class MushafLayoutModelTests(BaseTestCase):
    def test_mushaf_layout_where_name_duplicated_should_raise_integrity_error(self):
        # Arrange
        MushafLayout.objects.create(name="Madani 604", page_count=604)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            MushafLayout.objects.create(name="Madani 604", page_count=500)

    def test_mushaf_layout_where_page_count_is_zero_should_fail_validation(self):
        # Arrange
        layout = MushafLayout(name="Broken", page_count=0)

        # Act / Assert
        with self.assertRaises(ValidationError):
            layout.full_clean()

    def test_asset_template_choice_where_listed_should_expose_four_values(self):
        # Arrange / Act
        values = set(AssetTemplateChoice.values)

        # Assert
        self.assertEqual(values, {"surah", "ayah", "word", "page"})
