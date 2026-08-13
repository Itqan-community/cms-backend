from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura, Word
from apps.users.models import User


class HierarchyEndpointsTest(BaseTestCase):
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

    def test_list_hierarchy_tree_where_authenticated_should_return_sura_summaries(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/hierarchy/tree/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(
            body[0],
            {
                "id": 1,
                "name": "الفاتحة",
                "transliterated_name": "Al-Faatiha",
                "english_name": "The Opening",
                "ayas_count": 2,
                "start_offset": 0,
            },
        )

    def test_list_surah_ayah_tree_where_exists_should_return_ayahs_with_words_count_only(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/hierarchy/surah/1/tree/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(len(body), 2)
        self.assertEqual(body[0]["id"], 1)
        self.assertEqual(body[0]["number_in_sura"], 1)
        self.assertEqual(body[0]["words_count"], 2)
        self.assertEqual(body[1]["words_count"], 0)
        self.assertNotIn("words", body[0])
        self.assertNotIn("words", body[1])

    def test_list_surah_ayah_tree_where_sura_missing_should_return_404_sura_not_found(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/hierarchy/surah/999/tree/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual(response.json()["error_name"], "sura_not_found")

    def test_get_ayah_words_where_exists_should_return_ordered_words(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/hierarchy/ayah/1/1/words/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual([w["text"] for w in body], ["بِسْمِ", "اللَّهِ"])
        self.assertEqual([w["position_in_ayah"] for w in body], [1, 2])

    def test_get_ayah_words_where_ayah_missing_should_return_404_ayah_not_found(self):
        # Arrange
        user = baker.make(User, email="reader@example.com", is_active=True)
        self.authenticate_user(user)

        # Act
        response = self.client.get("/cms-api/hierarchy/ayah/1/99/words/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual(response.json()["error_name"], "ayah_not_found")

    def test_list_hierarchy_tree_where_unauthenticated_should_return_401(self):
        # Arrange / Act — cms_api mounts with internal_auth (SessionToken required)
        response = self.client.get("/cms-api/hierarchy/tree/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
