from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, CategoryChoice, StatusChoice
from apps.content.services.asset_content import AssetContentService
from apps.content.services.asset_language import AssetLanguageService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetLanguageServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="French Rashid",
            slug="french-rashid",
            language="ar",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayahs = [baker.make(Ayah, id=i, sura=self.sura, number_in_sura=i, text=f"ayah {i}") for i in (1, 2, 3)]

    def test_list_languages_creates_and_returns_source_first(self):
        AssetLanguage.objects.create(asset=self.translation, language="es")

        languages = AssetLanguageService().list_languages(self.translation.slug, CategoryChoice.TRANSLATION)

        self.assertTrue(languages[0].is_source)
        self.assertEqual("ar", languages[0].language)
        self.assertEqual({"ar", "es"}, {lang.language for lang in languages})

    def test_add_language_creates_non_source_row(self):
        lang = AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")

        self.assertFalse(lang.is_source)
        self.assertEqual("es", lang.language)

    def test_add_duplicate_language_raises(self):
        AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")

        with self.assertRaises(ItqanError):
            AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")

    def test_draft_is_per_language(self):
        svc = AssetContentService()
        AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")

        ar_draft = svc.get_or_create_draft(
            self.translation.slug, CategoryChoice.TRANSLATION, language="ar", created_by_id=self.user.id
        )
        es_draft = svc.get_or_create_draft(
            self.translation.slug, CategoryChoice.TRANSLATION, language="es", created_by_id=self.user.id
        )

        self.assertNotEqual(ar_draft.id, es_draft.id)
        self.assertEqual("ar", ar_draft.asset_language.language)
        self.assertEqual("es", es_draft.asset_language.language)

    def test_get_or_create_draft_unknown_language_raises(self):
        with self.assertRaises(ItqanError):
            AssetContentService().get_or_create_draft(
                self.translation.slug, CategoryChoice.TRANSLATION, language="zz", created_by_id=self.user.id
            )
