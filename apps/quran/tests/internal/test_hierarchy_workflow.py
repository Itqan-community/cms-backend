from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura, Word
from apps.users.models import User


class HierarchyWorkflowTest(BaseTestCase):
    """
    End-to-end drill-down: hierarchy tree → surah ayah tree → ayah words.
    Mirrors the lazy-load path the CMS frontend hierarchy manager will use.
    """

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
        baker.make(
            Ayah, id=2, sura=self.sura, number_in_sura=2, text="ٱلۡحَمۡدُ لِلَّهِ", juz=1, hizb_quarter=1, page=1
        )
        baker.make(Word, id=1, sura=self.sura, ayah=self.ayah1, position_in_ayah=1, text="بِسْمِ")
        baker.make(Word, id=2, sura=self.sura, ayah=self.ayah1, position_in_ayah=2, text="اللَّهِ")

    def test_hierarchy_drill_down_workflow_where_data_exists_should_lazy_load_words(self):
        # Arrange
        user = baker.make(User, email="workflow@example.com", is_active=True)
        self.authenticate_user(user)

        # Step 1: root tree
        tree_res = self.client.get("/cms-api/hierarchy/tree/")
        self.assertEqual(tree_res.status_code, 200, tree_res.content)
        suras = tree_res.json()
        self.assertGreaterEqual(len(suras), 1)
        sura_id = suras[0]["id"]
        self.assertEqual(suras[0]["ayas_count"], 2)
        self.assertEqual(suras[0]["start_offset"], 0)

        # Step 2: expand surah → ayahs with counts, no nested words
        ayah_tree_res = self.client.get(f"/cms-api/hierarchy/surah/{sura_id}/tree/")
        self.assertEqual(ayah_tree_res.status_code, 200, ayah_tree_res.content)
        ayahs = ayah_tree_res.json()
        self.assertEqual(len(ayahs), 2)
        for ayah in ayahs:
            self.assertNotIn("words", ayah)
            self.assertIn("words_count", ayah)

        ayah_with_words = next(a for a in ayahs if a["words_count"] > 0)
        self.assertEqual(ayah_with_words["words_count"], 2)

        # Step 3: expand ayah → ordered words; length matches words_count
        words_res = self.client.get(f"/cms-api/hierarchy/ayah/{sura_id}/{ayah_with_words['number_in_sura']}/words/")
        self.assertEqual(words_res.status_code, 200, words_res.content)
        words = words_res.json()
        self.assertEqual(len(words), ayah_with_words["words_count"])
        self.assertEqual([w["position_in_ayah"] for w in words], [1, 2])
        self.assertEqual([w["text"] for w in words], ["بِسْمِ", "اللَّهِ"])

    def test_hierarchy_drill_down_workflow_where_ayah_missing_should_return_ayah_not_found(self):
        # Arrange
        user = baker.make(User, email="workflow@example.com", is_active=True)
        self.authenticate_user(user)

        # Step 1–2: successful expands
        tree_res = self.client.get("/cms-api/hierarchy/tree/")
        self.assertEqual(tree_res.status_code, 200)
        sura_id = tree_res.json()[0]["id"]

        ayah_tree_res = self.client.get(f"/cms-api/hierarchy/surah/{sura_id}/tree/")
        self.assertEqual(ayah_tree_res.status_code, 200)
        self.assertEqual(len(ayah_tree_res.json()), 2)

        # Step 3: missing ayah after a valid expand
        words_res = self.client.get(f"/cms-api/hierarchy/ayah/{sura_id}/99/words/")
        self.assertEqual(words_res.status_code, 404)
        self.assertEqual(words_res.json()["error_name"], "ayah_not_found")
