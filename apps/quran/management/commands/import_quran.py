import csv
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.quran.models import Ayah, Sura, Word

SURAS_FILE = "quran-suras-list.xlsx - Sheet1.csv"
AYAS_FILE = "quran-ayas-list.xlsx - Sheet1.csv"
WORDS_FILE = "quran-words-list.xlsx - Sheet1.csv"

EXPECTED_SURAS = 114
EXPECTED_AYAHS = 6236
EXPECTED_WORDS = 77432

WORD_BATCH_SIZE = 2000


class Command(BaseCommand):
    help = "Import canonical Quran reference data (suras, ayahs, words) from the temp CSV files."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--path",
            type=str,
            default=str(Path(settings.BASE_DIR) / "temp" / "ayahs"),
            help="Directory containing the three Quran CSV files.",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Skip the canonical 114/6236/77432 count checks (e.g. when importing a fixture subset).",
        )

    def _read_rows(self, directory: Path, filename: str) -> list[dict[str, str]]:
        file_path = directory / filename
        if not file_path.exists():
            raise CommandError(f"CSV file not found: {file_path}")
        with file_path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        directory = Path(options["path"])
        self.stdout.write(f"Reading Quran CSVs from: {directory}")

        sura_rows = self._read_rows(directory, SURAS_FILE)
        aya_rows = self._read_rows(directory, AYAS_FILE)
        word_rows = self._read_rows(directory, WORDS_FILE)

        # Clear existing data so the command is fully idempotent. Deleting suras
        # cascades to ayahs and words.
        Word.objects.all().delete()
        Ayah.objects.all().delete()
        Sura.objects.all().delete()

        suras = [
            Sura(
                id=int(row["id"]),
                name=row["name"],
                transliterated_name=row["tname"],
                english_name=row["ename"],
                ayas_count=int(row["ayas"]),
                start_offset=int(row["start"]),
                revelation_type=row["type"],
                revelation_order=int(row["order"]),
                rukus_count=int(row["rukus"]),
            )
            for row in sura_rows
        ]
        Sura.objects.bulk_create(suras, batch_size=WORD_BATCH_SIZE)

        ayahs = [
            Ayah(
                id=int(row["id"]),
                sura_id=int(row["sura_id"]),
                number_in_sura=int(row["index"]),
                text=row["text"],
                juz=int(row["juz"]),
                hizb_quarter=int(row["quarter"]),
                page=int(row["page"]),
            )
            for row in aya_rows
        ]
        Ayah.objects.bulk_create(ayahs, batch_size=WORD_BATCH_SIZE)

        words = [
            Word(
                id=int(row["id"]),
                sura_id=int(row["sura_id"]),
                ayah_id=int(row["aya_id"]),
                position_in_ayah=int(row["aya_index"]),
                text=row["word"],
            )
            for row in word_rows
        ]
        Word.objects.bulk_create(words, batch_size=WORD_BATCH_SIZE)

        sura_count = Sura.objects.count()
        ayah_count = Ayah.objects.count()
        word_count = Word.objects.count()

        self.stdout.write(f"Imported {sura_count} suras, {ayah_count} ayahs, {word_count} words.")

        if options["skip_validation"]:
            self.stdout.write(self.style.SUCCESS("Quran reference data imported (validation skipped)."))
            return

        if sura_count != EXPECTED_SURAS:
            raise CommandError(f"Expected {EXPECTED_SURAS} suras, got {sura_count}.")
        if ayah_count != EXPECTED_AYAHS:
            raise CommandError(f"Expected {EXPECTED_AYAHS} ayahs, got {ayah_count}.")
        if word_count != EXPECTED_WORDS:
            raise CommandError(f"Expected {EXPECTED_WORDS} words, got {word_count}.")

        self.stdout.write(self.style.SUCCESS("Quran reference data imported successfully."))
