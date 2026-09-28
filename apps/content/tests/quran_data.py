"""Minimal Quran rows for tests.

The test database ships with zero Sura/Ayah/Word rows and there is no global
fixture, so each test class bakes exactly what it asserts against. Fields are
populated explicitly rather than left to baker so the numbers in assertions
are traceable to something readable here.

Shape: 2 suras, 3 ayahs (2 in sura 1, 1 in sura 2), 2 words (both in ayah 1).
Downstream tests assert against those counts — changing them breaks Tasks 5,
6, 7, 7A, 11 and 12.
"""

from model_bakery import baker

from apps.quran.models import Ayah, Sura, Word


class QuranDataMixin:
    def bake_quran(self) -> None:
        """Bake the minimal Quran slice as instance attributes."""
        self.sura1 = baker.make(
            Sura,
            id=1,
            name="الفاتحة",
            transliterated_name="Al-Fatiha",
            english_name="The Opening",
            ayas_count=2,
            start_offset=0,
            revelation_type="Meccan",
            revelation_order=5,
            rukus_count=1,
        )
        self.sura2 = baker.make(
            Sura,
            id=2,
            name="البقرة",
            transliterated_name="Al-Baqara",
            english_name="The Cow",
            ayas_count=1,
            start_offset=2,
            revelation_type="Medinan",
            revelation_order=87,
            rukus_count=1,
        )
        self.ayah1 = baker.make(
            Ayah, id=1, sura=self.sura1, number_in_sura=1, text="ayah 1", juz=1, hizb_quarter=1, page=1
        )
        self.ayah2 = baker.make(
            Ayah, id=2, sura=self.sura1, number_in_sura=2, text="ayah 2", juz=1, hizb_quarter=1, page=1
        )
        self.ayah3 = baker.make(
            Ayah, id=3, sura=self.sura2, number_in_sura=1, text="ayah 3", juz=1, hizb_quarter=1, page=2
        )
        self.word1 = baker.make(Word, id=1, sura=self.sura1, ayah=self.ayah1, position_in_ayah=1, text="w1")
        self.word2 = baker.make(Word, id=2, sura=self.sura1, ayah=self.ayah1, position_in_ayah=2, text="w2")
