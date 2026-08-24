"""Tests for Quran sample endpoints (surah, ayah)."""

from django.test import TestCase
from model_bakery import baker

from apps.quran.models import Ayah, Sura


class QuranSamplesTest(TestCase):
    """Tests for /sample-data/surah/ and /sample-data/ayah/ endpoints."""

    def setUp(self) -> None:
        self.sura1 = baker.make(
            Sura,
            id=1,
            name="الفاتحة",
            transliterated_name="Al-Faatiha",
            english_name="The Opening",
            ayas_count=7,
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
            ayas_count=286,
            start_offset=7,
            revelation_type="Medinan",
            revelation_order=87,
            rukus_count=40,
        )
        self.ayah11 = baker.make(
            Ayah,
            id=1,
            sura=self.sura1,
            number_in_sura=1,
            text="بِسۡمِ ٱللَّهِ ٱلرَّحۡمَـٰنِ ٱلرَّحِيمِ",
            juz=1,
            hizb_quarter=1,
            page=1,
        )
        self.ayah12 = baker.make(
            Ayah,
            id=2,
            sura=self.sura1,
            number_in_sura=2,
            text="ٱلۡحَمۡدُ لِلَّهِ رَبِّ ٱلۡعَـٰلَمِينَ",
            juz=1,
            hizb_quarter=1,
            page=1,
        )

    def test_get_surah_sample_with_default_query_should_return_surah_1(self):
        # Act
        response = self.client.get("/sample-data/surah/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, data["id"])
        self.assertEqual("الفاتحة", data["name"])
        self.assertEqual("Al-Faatiha", data["transliterated_name"])
        self.assertEqual("The Opening", data["english_name"])
        self.assertEqual(7, data["ayas_count"])

    def test_get_surah_sample_with_explicit_surah_should_return_that_surah(self):
        # Act
        response = self.client.get("/sample-data/surah/", {"surah": 2})
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(2, data["id"])
        self.assertEqual("البقرة", data["name"])

    def test_get_surah_sample_where_surah_does_not_exist_should_return_404(self):
        # Arrange
        Sura.objects.filter(id=3).delete()
        # Act
        response = self.client.get("/sample-data/surah/", {"surah": 3})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("sura_not_found", response.json()["error_name"])

    def test_get_surah_sample_where_surah_out_of_range_should_return_validation_error(self):
        # Act
        response = self.client.get("/sample-data/surah/", {"surah": 115})
        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])

    def test_get_ayah_sample_with_default_query_should_return_ayah_1_1(self):
        # Act
        response = self.client.get("/sample-data/ayah/")
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        expected_keys = {
            "id",
            "surah_id",
            "number_in_surah",
            "text_uthmani",
            "juz",
            "page",
            "hizb_quarter",
        }
        self.assertEqual(expected_keys, set(data.keys()))
        self.assertEqual(1, data["id"])
        self.assertEqual(1, data["surah_id"])
        self.assertEqual(1, data["number_in_surah"])
        self.assertEqual("بِسۡمِ ٱللَّهِ ٱلرَّحۡمَـٰنِ ٱلرَّحِيمِ", data["text_uthmani"])
        self.assertEqual(1, data["juz"])
        self.assertEqual(1, data["page"])
        self.assertEqual(1, data["hizb_quarter"])

    def test_get_ayah_sample_with_explicit_query_should_return_requested_ayah(self):
        # Act
        response = self.client.get("/sample-data/ayah/", {"surah": 1, "ayah": 2})
        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, data["surah_id"])
        self.assertEqual(2, data["number_in_surah"])
        self.assertEqual("ٱلۡحَمۡدُ لِلَّهِ رَبِّ ٱلۡعَـٰلَمِينَ", data["text_uthmani"])

    def test_get_ayah_sample_where_ayah_does_not_exist_should_return_404(self):
        # Act
        response = self.client.get("/sample-data/ayah/", {"surah": 1, "ayah": 8})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("ayah_not_found", response.json()["error_name"])

    def test_get_ayah_sample_where_surah_does_not_exist_should_return_sura_not_found(self):
        # Act
        response = self.client.get("/sample-data/ayah/", {"surah": 114, "ayah": 1})
        # Assert
        self.assertEqual(404, response.status_code)
        self.assertEqual("sura_not_found", response.json()["error_name"])

    def test_get_ayah_sample_where_ayah_below_allowed_minimum_should_return_validation_error(self):
        # Act
        response = self.client.get("/sample-data/ayah/", {"surah": 1, "ayah": 0})
        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("validation_error", response.json()["error_name"])
