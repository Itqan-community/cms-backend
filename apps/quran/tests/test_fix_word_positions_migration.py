import importlib

from django.apps import apps as django_apps
from django.db import connection
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura, Word

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.quran.migrations.0002_fix_word_positions")


class FixWordPositionsMigrationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        sura = baker.make(Sura, id=1)
        self.ayah1 = baker.make(Ayah, id=1, sura=sura, number_in_sura=1)
        self.ayah2 = baker.make(Ayah, id=2, sura=sura, number_in_sura=2)

    def _run(self) -> None:
        with connection.schema_editor() as schema_editor:
            migration.fix_word_positions(django_apps, schema_editor)

    def test_fix_word_positions_where_ayah_number_was_stored_should_number_words_in_reading_order(self):
        # Arrange: what the old importer wrote — every word carries its ayah number.
        for word_id, ayah in [(1, self.ayah1), (2, self.ayah1), (3, self.ayah1), (4, self.ayah2), (5, self.ayah2)]:
            baker.make(Word, id=word_id, sura_id=1, ayah=ayah, position_in_ayah=ayah.number_in_sura)

        # Act
        self._run()

        # Assert
        positions = list(Word.objects.order_by("id").values_list("id", "position_in_ayah"))
        self.assertEqual(positions, [(1, 1), (2, 2), (3, 3), (4, 1), (5, 2)])

    def test_fix_word_positions_where_already_correct_should_leave_rows_unchanged(self):
        # Arrange
        baker.make(Word, id=1, sura_id=1, ayah=self.ayah1, position_in_ayah=1)
        baker.make(Word, id=2, sura_id=1, ayah=self.ayah1, position_in_ayah=2)

        # Act
        self._run()
        self._run()

        # Assert
        self.assertEqual(list(Word.objects.order_by("id").values_list("position_in_ayah", flat=True)), [1, 2])

    def test_fix_word_positions_where_no_words_should_do_nothing(self):
        # Arrange: no Word rows.

        # Act
        self._run()

        # Assert
        self.assertFalse(Word.objects.exists())
