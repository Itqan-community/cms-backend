from io import StringIO
from pathlib import Path

from django.core.management import call_command

from apps.core.tests.base import BaseTestCase
from apps.quran.models import Word

FIXTURES = Path(__file__).parent / "fixtures"


class ImportQuranCommandTests(BaseTestCase):
    def test_import_quran_where_ayah_has_several_words_should_number_them_in_reading_order(self):
        # Arrange: the fixture's aya_index column holds the ayah number, not the
        # word position (both words of 1:1 carry aya_index 1).

        # Act
        call_command("import_quran", path=str(FIXTURES), skip_validation=True, stdout=StringIO())

        # Assert
        positions = list(Word.objects.order_by("id").values_list("id", "ayah_id", "position_in_ayah"))
        self.assertEqual(positions, [(1, 1, 1), (2, 1, 2), (3, 2, 1)])
