from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.quran.models import Ayah, Sura, Word

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ImportQuranCommandTest(TestCase):
    def test_import_quran_where_valid_csvs_should_populate_all_tables(self):
        # Arrange
        # (fixtures: 1 sura, 2 ayahs, 3 words)

        # Act
        call_command("import_quran", path=str(FIXTURES_DIR), skip_validation=True)

        # Assert
        self.assertEqual(Sura.objects.count(), 1)
        self.assertEqual(Ayah.objects.count(), 2)
        self.assertEqual(Word.objects.count(), 3)

    def test_import_quran_where_run_should_map_foreign_keys_and_fields(self):
        # Arrange

        # Act
        call_command("import_quran", path=str(FIXTURES_DIR), skip_validation=True)

        # Assert
        sura = Sura.objects.get(pk=1)
        self.assertEqual(sura.name, "الفاتحة")
        self.assertEqual(sura.transliterated_name, "Al-Faatiha")
        self.assertEqual(sura.ayas_count, 2)
        self.assertEqual(sura.revelation_type, "Meccan")

        ayah = Ayah.objects.get(pk=2)
        self.assertEqual(ayah.sura_id, 1)
        self.assertEqual(ayah.number_in_sura, 2)
        self.assertEqual(ayah.page, 1)

        # Words of ayah 1 are returned in canonical order
        ayah_one_words = list(Ayah.objects.get(pk=1).words.values_list("text", flat=True))
        self.assertEqual(ayah_one_words, ["بِسْمِ", "اللَّهِ"])

    def test_import_quran_where_run_twice_should_be_idempotent(self):
        # Arrange
        call_command("import_quran", path=str(FIXTURES_DIR), skip_validation=True)

        # Act
        call_command("import_quran", path=str(FIXTURES_DIR), skip_validation=True)

        # Assert
        self.assertEqual(Sura.objects.count(), 1)
        self.assertEqual(Ayah.objects.count(), 2)
        self.assertEqual(Word.objects.count(), 3)
