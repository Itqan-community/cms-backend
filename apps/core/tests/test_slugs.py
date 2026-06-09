from django.test import SimpleTestCase

from apps.core.slugs import slugify_name, slugify_text


class SlugifyTextTest(SimpleTestCase):
    def test_english_passes_through(self):
        self.assertEqual("tafsir-center", slugify_text("Tafsir Center"))

    def test_arabic_is_transliterated_to_latin(self):
        slug = slugify_text("مركز التفسير")
        self.assertTrue(slug.isascii())
        self.assertEqual("mrkz-ltfsyr", slug)

    def test_empty_and_none(self):
        self.assertEqual("", slugify_text(""))
        self.assertEqual("", slugify_text(None))


class SlugifyNameTest(SimpleTestCase):
    def test_prefers_english_when_provided(self):
        self.assertEqual("new-reciter", slugify_name("New Reciter", "مقرئ جديد"))

    def test_falls_back_to_arabic_when_english_missing(self):
        slug = slugify_name("", "سعد الغامدي")
        self.assertTrue(slug.isascii())
        self.assertEqual("sd-lgmdy", slug)

    def test_falls_back_to_arabic_when_english_none(self):
        self.assertEqual("sd-lgmdy", slugify_name(None, "سعد الغامدي"))

    def test_blank_english_is_ignored(self):
        self.assertEqual("mrkz-ltfsyr", slugify_name("   ", "مركز التفسير"))

    def test_both_empty_returns_empty(self):
        self.assertEqual("", slugify_name("", ""))
        self.assertEqual("", slugify_name(None, None))
