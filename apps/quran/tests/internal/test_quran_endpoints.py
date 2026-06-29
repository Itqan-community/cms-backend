from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura, Word
from apps.users.models import User


class QuranEndpointsTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sura = baker.make(
            Sura,
            id=1,
            name="الفاتحة",
            transliterated_name="Al-Faatiha",
            english_name="The Opening",
            ayas_count=2,
            start_offset=0,
            revelation_type="Meccan",
            revelation_order=5,
            rukus_count=1,
        )
        self.ayah1 = baker.make(
            Ayah, id=1, sura=self.sura, number_in_sura=1, text="بِسۡمِ ٱللَّهِ", juz=1, hizb_quarter=1, page=1
        )
        self.ayah2 = baker.make(
            Ayah, id=2, sura=self.sura, number_in_sura=2, text="ٱلۡحَمۡدُ لِلَّهِ", juz=1, hizb_quarter=1, page=1
        )
        baker.make(Word, id=1, sura=self.sura, ayah=self.ayah1, position_in_ayah=1, text="بِسْمِ")
        baker.make(Word, id=2, sura=self.sura, ayah=self.ayah1, position_in_ayah=2, text="اللَّهِ")

    def test_list_suras_where_authenticated_should_return_all_suras(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/suras/")

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["transliterated_name"], "Al-Faatiha")

    def test_get_ayah_where_exists_should_return_ayah_with_ordered_words(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/suras/1/ayahs/1/")

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["sura_id"], 1)
        self.assertEqual(body["number_in_sura"], 1)
        self.assertEqual([w["text"] for w in body["words"]], ["بِسْمِ", "اللَّهِ"])

    def test_get_sura_where_missing_should_return_404_sura_not_found(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/suras/999/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "sura_not_found")

    def test_get_ayah_where_ayah_missing_should_return_404_ayah_not_found(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/suras/1/ayahs/99/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "ayah_not_found")
