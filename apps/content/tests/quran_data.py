from model_bakery import baker

from apps.quran.models import Ayah, Sura, Word


class QuranDataMixin:
    """Bakes a small, internally-consistent slice of canonical Quran data.

    The test database ships with zero Sura/Ayah/Word rows and there is no
    global fixture for them, so any test that needs real Quran reference rows
    (rather than baking ad hoc rows inline) calls ``self.bake_quran()``.

    Bakes sura 1 (Al-Fatiha) and sura 2 (Al-Baqara), one ayah in each, and one
    word in the first ayah — enough to key an entry/change to any of the four
    unit types (sura, ayah, word, page) without colliding with each other.
    """

    def bake_quran(self) -> None:
        """Bake sura 1-2 with one ayah each and one word, as instance attributes."""
        self.sura_1 = baker.make(
            Sura,
            id=1,
            name="الفاتحة",
            transliterated_name="Al-Fatiha",
            english_name="The Opening",
            ayas_count=7,
            start_offset=0,
            revelation_type="Meccan",
            revelation_order=5,
            rukus_count=1,
        )
        self.sura_2 = baker.make(
            Sura,
            id=2,
            name="البقرة",
            transliterated_name="Al-Baqara",
            english_name="The Cow",
            ayas_count=286,
            start_offset=7,
            revelation_type="Medinan",
            revelation_order=87,
            rukus_count=40,
        )
        self.ayah_1_1 = baker.make(
            Ayah,
            id=1,
            sura=self.sura_1,
            number_in_sura=1,
            text="بسم الله الرحمن الرحيم",
            juz=1,
            hizb_quarter=1,
            page=1,
        )
        self.ayah_2_1 = baker.make(
            Ayah,
            id=8,
            sura=self.sura_2,
            number_in_sura=1,
            text="الم",
            juz=1,
            hizb_quarter=1,
            page=2,
        )
        self.word_1 = baker.make(
            Word,
            id=1,
            sura=self.sura_1,
            ayah=self.ayah_1_1,
            position_in_ayah=1,
            text="بسم",
        )
