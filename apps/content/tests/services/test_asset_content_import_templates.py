from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class TemplateImportTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def _spec(self, template, layout=None):
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=template, mushaf_layout=layout)
        return unit_spec_for(asset), asset

    def test_parse_where_surah_file_should_key_by_surah_number(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.SURAH)
        raw = b"surah,text\n1,opening\n2,cow\n"  # surahs 1 and 2 baked by bake_quran

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual([(p.unit_id, p.cells["text"]) for p in parsed], [(1, "opening"), (2, "cow")])

    def test_parse_where_page_file_should_key_by_page_number(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        spec, asset = self._spec(AssetTemplateChoice.PAGE, layout=layout)
        raw = b"page,text\n1,first\n604,last\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual([(p.unit_id, p.cells["text"]) for p in parsed], [(1, "first"), (604, "last")])

    def test_parse_where_word_file_has_word_id_should_prefer_it(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.WORD)
        # word id 2 is baked; the surah/ayah/word triple is deliberately bogus so
        # only word_id precedence can satisfy the assertion
        raw = b"word_id,surah,ayah,word,text\n2,99,99,99,gloss\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual(parsed[0].unit_id, 2)

    def test_parse_where_word_file_has_no_word_id_should_resolve_triple(self):
        # Arrange: word 2 is (surah 1, ayah-in-surah 1, position-in-ayah 2) per bake_quran
        spec, asset = self._spec(AssetTemplateChoice.WORD)
        raw = b"surah,ayah,word,text\n1,1,2,gloss\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual(parsed[0].unit_id, self.word2.id)
        self.assertEqual(parsed[0].cells["text"], "gloss")

    def test_parse_where_headers_use_legacy_sura_aya_spelling_should_still_import(self):
        # Arrange: files exported before the Marqoom rename name the units sura / aya
        surah_spec, surah_asset = self._spec(AssetTemplateChoice.SURAH)
        word_spec, word_asset = self._spec(AssetTemplateChoice.WORD)

        # Act
        surah_parsed = parse_content_file(b"sura,text\n2,cow\n", surah_spec, surah_asset)
        word_parsed = parse_content_file(b"sura,aya,word,text\n1,1,2,gloss\n", word_spec, word_asset)

        # Assert
        self.assertEqual([(p.unit_id, p.cells["text"]) for p in surah_parsed], [(2, "cow")])
        self.assertEqual([(p.unit_id, p.cells["text"]) for p in word_parsed], [(self.word2.id, "gloss")])

    def test_parse_where_ayah_file_should_keep_working(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.AYAH)
        raw = b"id,surah,ayah,translation\n1,1,1,bismillah\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual(parsed[0].unit_id, 1)
        self.assertEqual(parsed[0].cells["text"], "bismillah")

    def test_parse_where_columns_do_not_match_template_should_raise(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        spec, asset = self._spec(AssetTemplateChoice.PAGE, layout=layout)
        raw = b"surah,ayah,text\n1,1,x\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, spec, asset)

    def test_parse_where_surah_id_out_of_range_should_raise(self):
        # Arrange: only surahs 1 and 2 exist (baked by bake_quran)
        spec, asset = self._spec(AssetTemplateChoice.SURAH)
        raw = b"surah,text\n999,bogus\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, spec, asset)

    def test_parse_where_page_out_of_layout_range_should_raise(self):
        # Arrange: layout only has 604 pages
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        spec, asset = self._spec(AssetTemplateChoice.PAGE, layout=layout)
        raw = b"page,text\n700,bogus\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, spec, asset)

    def test_parse_where_word_file_missing_recognised_columns_should_raise(self):
        # Arrange: neither word_id nor the surah/ayah/word triple is present
        spec, asset = self._spec(AssetTemplateChoice.WORD)
        raw = b"foo,text\n1,gloss\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, spec, asset)
