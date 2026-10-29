"""Minimal Quran rows for group-template (ayah_group / word_group) tests.

Separate from ``QuranDataMixin``, whose counts many tests assert against.

Shape: 2 surahs; 5 ayahs — 1:1, 1:2, 1:3, 2:1, 2:2 (ids 1-5, text "a1"…"a5");
8 words — ayah 1 has words 1-3, ayah 2 has 4-5, ayah 3 has 6, ayah 4 has 7-8
(text "w1"…"w8"). Group tests assert labels and reference texts built from
these numbers, so changing them breaks those tests.
"""

from model_bakery import baker

from apps.quran.models import Ayah, Surah, Word

# (surah, number_in_surah) of ayah ids 1-5.
_AYAHS = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)]
# Ayah id of word ids 1-8.
_WORD_AYAHS = [1, 1, 1, 2, 2, 3, 4, 4]


class GroupQuranDataMixin:
    def bake_group_quran(self) -> None:
        """Bake the slice as ``self.surahs``, ``self.ayahs`` and ``self.words`` (index 0 = id 1)."""
        self.surahs = [
            baker.make(
                Surah,
                id=1,
                name="الفاتحة",
                transliterated_name="Al-Fatiha",
                english_name="The Opening",
                ayahs_count=3,
                start_offset=0,
                revelation_type="Meccan",
                revelation_order=5,
                rukus_count=1,
            ),
            baker.make(
                Surah,
                id=2,
                name="البقرة",
                transliterated_name="Al-Baqara",
                english_name="The Cow",
                ayahs_count=2,
                start_offset=3,
                revelation_type="Medinan",
                revelation_order=87,
                rukus_count=1,
            ),
        ]
        self.ayahs = [
            baker.make(
                Ayah,
                id=index,
                surah_id=surah,
                number_in_surah=number,
                text=f"a{index}",
                juz=1,
                hizb_quarter=1,
                page=1,
            )
            for index, (surah, number) in enumerate(_AYAHS, start=1)
        ]
        self.words = []
        for index, ayah_id in enumerate(_WORD_AYAHS, start=1):
            ayah = self.ayahs[ayah_id - 1]
            position = _WORD_AYAHS[:index].count(ayah_id)
            self.words.append(
                baker.make(
                    Word, id=index, surah_id=ayah.surah_id, ayah=ayah, position_in_ayah=position, text=f"w{index}"
                )
            )
