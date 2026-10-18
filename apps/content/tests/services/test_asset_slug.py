from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, Reciter, Riwayah
from apps.content.services.asset_slug import AssetSlugService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class AssetSlugFromWordsTests(BaseTestCase):
    def test_slug_from_words_where_tafsir_should_prefix_category(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(category=CategoryChoice.TAFSIR, words=["Ibn", "Kathir"])

        # Assert
        self.assertEqual("tafsir-ibn-kathir", slug)

    def test_slug_from_words_where_words_repeat_category_should_strip_it(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(category=CategoryChoice.TAFSIR, words=["tafsir", "ibn", "kathir"])

        # Assert
        self.assertEqual("tafsir-ibn-kathir", slug)

    def test_slug_from_words_where_translation_should_include_language(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(
            category=CategoryChoice.TRANSLATION, words=["sahih", "international"], language="EN"
        )

        # Assert
        self.assertEqual("translation-en-sahih-international", slug)

    def test_slug_from_words_where_recitation_should_allow_reciter_and_riwayah_words(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(
            category=CategoryChoice.RECITATION, words=["mishary", "rashid", "alafasy", "hafs"]
        )

        # Assert
        self.assertEqual("recitation-mishary-rashid-alafasy-hafs", slug)

    def test_slug_from_words_where_words_are_junk_should_sanitize_and_truncate(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(category=CategoryChoice.MUSHAF, words=["مصحف!!", "Ḥafṣ", "x" * 80, "", "  ", 3])

        # Assert
        self.assertRegex(slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(slug), 50)
        self.assertTrue(slug.startswith("mushaf-"))

    def test_slug_from_words_where_no_usable_words_should_return_none(self):
        # Arrange
        service = AssetSlugService()

        # Act / Assert
        for words in ([], ["", "!!"], ["mushaf"], None, "not-a-list"):
            with self.subTest(words=words):
                self.assertIsNone(service.slug_from_words(category=CategoryChoice.MUSHAF, words=words))

    def test_slug_from_words_where_slug_taken_should_append_counter(self):
        # Arrange
        baker.make(Asset, slug="font-uthmanic-hafs", category=CategoryChoice.FONT)
        baker.make(Asset, slug="font-uthmanic-hafs-2", category=CategoryChoice.FONT)
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(category=CategoryChoice.FONT, words=["uthmanic", "hafs"])

        # Assert
        self.assertEqual("font-uthmanic-hafs-3", slug)

    def test_slug_from_words_where_recitation_taken_and_year_set_should_append_year_first(self):
        # Arrange
        baker.make(Asset, slug="recitation-mishary-alafasy", category=CategoryChoice.MUSHAF)
        service = AssetSlugService()

        # Act
        slug = service.slug_from_words(category=CategoryChoice.RECITATION, words=["mishary", "alafasy"], year=2005)

        # Assert
        self.assertEqual("recitation-mishary-alafasy-2005", slug)


class AssetSlugPromptTests(BaseTestCase):
    def test_slug_prompt_where_recitation_should_name_reciter_and_riwayah(self):
        # Arrange
        reciter = baker.make(Reciter, name_en="", name_ar="سعد الغامدي")
        riwayah = baker.make(Riwayah, name_en="Hafs", name_ar="حفص")
        service = AssetSlugService()

        # Act
        prompt = service.slug_prompt(
            category=CategoryChoice.RECITATION,
            name_ar="تلاوة",
            name_en="",
            reciter_id=reciter.pk,
            riwayah_id=riwayah.pk,
        )

        # Assert
        self.assertIn("سعد الغامدي", prompt)
        self.assertIn("Hafs", prompt)
        self.assertNotIn("تلاوة", prompt)

    def test_slug_prompt_where_tafsir_should_include_both_names(self):
        # Arrange
        service = AssetSlugService()

        # Act
        prompt = service.slug_prompt(
            category=CategoryChoice.TAFSIR, name_ar="تفسير ابن كثير", name_en="Tafsir Ibn Kathir"
        )

        # Assert
        self.assertIn("تفسير ابن كثير", prompt)
        self.assertIn("Tafsir Ibn Kathir", prompt)


class AssetSlugBuildTests(BaseTestCase):
    def test_build_slug_where_english_name_should_use_template_without_ai(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.build_slug(
            category=CategoryChoice.MUSHAF, name_en="Madinah Mushaf Hafs Edition 1441", name_ar=""
        )

        # Assert
        self.assertEqual("mushaf-madinah-hafs-edition", slug)

    def test_build_slug_where_recitation_should_use_reciter_and_riwayah_names(self):
        # Arrange
        reciter = baker.make(Reciter, name_en="Mishary Alafasy", name_ar="مشاري العفاسي")
        riwayah = baker.make(Riwayah, name_en="Hafs", name_ar="حفص")
        service = AssetSlugService()

        # Act
        slug = service.build_slug(
            category=CategoryChoice.RECITATION,
            name_en="",
            name_ar="تلاوة",
            reciter_id=reciter.pk,
            riwayah_id=riwayah.pk,
        )

        # Assert
        self.assertEqual("recitation-mishary-alafasy-hafs", slug)

    def test_build_slug_where_no_name_at_all_should_return_category_only(self):
        # Arrange
        service = AssetSlugService()

        # Act / Assert
        self.assertEqual("mushaf", service.build_slug(category=CategoryChoice.MUSHAF, name_en="", name_ar=""))


class AssetSlugResolveTests(BaseTestCase):
    def test_resolve_slug_where_nothing_requested_should_build_from_names(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.resolve_slug(
            category=CategoryChoice.TAFSIR, requested=None, name_en="Tafsir Al Saadi", name_ar=""
        )

        # Assert
        self.assertEqual("tafsir-al-saadi", slug)

    def test_resolve_slug_where_valid_slug_requested_should_keep_it(self):
        # Arrange
        service = AssetSlugService()

        # Act
        slug = service.resolve_slug(
            category=CategoryChoice.TAFSIR, requested="tafsir-ibn-kathir", name_en="", name_ar="تفسير"
        )

        # Assert
        self.assertEqual("tafsir-ibn-kathir", slug)

    def test_resolve_slug_where_requested_slug_taken_should_append_counter(self):
        # Arrange
        baker.make(Asset, slug="tafsir-ibn-kathir", category=CategoryChoice.MUSHAF)
        service = AssetSlugService()

        # Act
        slug = service.resolve_slug(
            category=CategoryChoice.TAFSIR, requested="tafsir-ibn-kathir", name_en="", name_ar="تفسير"
        )

        # Assert
        self.assertEqual("tafsir-ibn-kathir-2", slug)

    def test_resolve_slug_where_requested_slug_malformed_should_raise_asset_slug_invalid(self):
        # Arrange
        service = AssetSlugService()
        bad = ["Tafsir-Ibn", "tafsir_ibn", "tafsir--ibn", "tafsir-", "tafsir-تفسير", "tafsir-" + "x" * 50]

        for requested in bad:
            with self.subTest(requested=requested):
                # Act / Assert
                with self.assertRaises(ItqanError) as ctx:
                    service.resolve_slug(category=CategoryChoice.TAFSIR, requested=requested, name_en="", name_ar="x")
                self.assertEqual("asset_slug_invalid", ctx.exception.error_name)

    def test_resolve_slug_where_requested_slug_has_other_category_prefix_should_raise_asset_slug_invalid(self):
        # Arrange
        service = AssetSlugService()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.resolve_slug(category=CategoryChoice.MUSHAF, requested="tafsir-ibn-kathir", name_en="", name_ar="x")
        self.assertEqual("asset_slug_invalid", ctx.exception.error_name)
