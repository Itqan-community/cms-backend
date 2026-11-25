from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, StatusChoice
from apps.content.services.asset_content_import import (
    AssetContentColumnMappingError,
    AssetContentMissingColumnsError,
    parse_content_file,
)
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class ColumnMappingImportTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TEXT, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        self.spec = unit_spec_for(self.asset)

    def test_parse_content_file_where_mapping_names_unknown_headers_should_parse(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,In the name\n1,2,Praise\n"

        # Act
        parsed = parse_content_file(
            raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": 1, "text": 2}
        )

        # Assert
        self.assertEqual(
            [(p.unit_id, p.cells) for p in parsed],
            [(self.ayah1.id, {"text": "In the name"}), (self.ayah2.id, {"text": "Praise"})],
        )

    def test_parse_content_file_where_mapping_given_should_override_alias_matching(self):
        # Arrange — "translation" would be matched by alias; the mapping picks "fixed" instead
        raw = b"surah,ayah,translation,fixed\n1,1,old,new\n"

        # Act
        parsed = parse_content_file(
            raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": 1, "text": 3}
        )

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.ayah1.id, {"text": "new"})])

    def test_parse_content_file_where_mapping_has_preamble_should_keep_file_row_numbers(self):
        # Arrange
        raw = b"Exported\nchapter,verse,meaning\n1,1,x\n1,1,y\n"

        # Act / Assert — the duplicate is reported at its row in the file
        with self.assertRaisesMessage(Exception, "{4: 'duplicate'}"):
            parse_content_file(
                raw,
                self.spec,
                self.asset,
                column_keys=["text"],
                strict=True,
                column_mapping={"surah": 0, "ayah": 1, "text": 2},
            )

    def test_parse_content_file_where_two_columns_mapped_should_parse_both_and_ignore_extras(self):
        # Arrange
        raw = b"s,a,q,notes,ans\n1,1,Q1,ignored,A1\n"

        # Act
        parsed = parse_content_file(
            raw,
            self.spec,
            self.asset,
            column_keys=["question", "answer"],
            column_mapping={"surah": 0, "ayah": 1, "question": 2, "answer": 4},
        )

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.ayah1.id, {"question": "Q1", "answer": "A1"})])

    def test_parse_content_file_where_mapping_misses_required_field_should_raise_incomplete(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,x\n"

        # Act
        with self.assertRaises(AssetContentColumnMappingError) as raised:
            parse_content_file(
                raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": None}
            )

        # Assert
        self.assertTrue(raised.exception.incomplete)
        self.assertEqual(raised.exception.fields, ["ayah", "text"])

    def test_parse_content_file_where_mapping_reuses_a_column_should_raise_invalid(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,x\n"

        # Act
        with self.assertRaises(AssetContentColumnMappingError) as raised:
            parse_content_file(
                raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": 0, "text": 2}
            )

        # Assert
        self.assertFalse(raised.exception.incomplete)
        self.assertEqual(raised.exception.fields, ["surah", "ayah"])

    def test_parse_content_file_where_mapping_names_unknown_field_or_column_should_raise_invalid(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,x\n"

        # Act
        with self.assertRaises(AssetContentColumnMappingError) as unknown_field:
            parse_content_file(raw, self.spec, self.asset, column_keys=["text"], column_mapping={"page": 0})
        with self.assertRaises(AssetContentColumnMappingError) as past_header:
            parse_content_file(
                raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": 1, "text": 9}
            )

        # Assert
        self.assertEqual(unknown_field.exception.fields, ["page"])
        self.assertEqual(past_header.exception.fields, ["text"])

    def test_parse_content_file_where_word_template_mapped_by_triple_should_parse(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TEXT, template=AssetTemplateChoice.WORD, status=StatusChoice.READY
        )
        raw = b"s,a,w,gloss\n1,1,2,praise\n"

        # Act
        parsed = parse_content_file(
            raw,
            unit_spec_for(asset),
            asset,
            column_keys=["text"],
            column_mapping={"surah": 0, "ayah": 1, "word": 2, "text": 3},
        )

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.word2.id, {"text": "praise"})])

    def test_parse_content_file_where_no_mapping_should_keep_alias_matching(self):
        # Arrange
        raw = b"surah,ayah,answer\n1,1,A1\n"

        # Act / Assert — unchanged behaviour for clients that send no mapping
        with self.assertRaises(AssetContentMissingColumnsError):
            parse_content_file(raw, self.spec, self.asset, column_keys=["question", "answer"])
