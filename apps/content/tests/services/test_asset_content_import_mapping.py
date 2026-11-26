from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, StatusChoice
from apps.content.services.asset_content_import import (
    PREVIEW_BYTES,
    AssetContentColumnMappingError,
    AssetContentMissingColumnsError,
    AssetContentParseError,
    parse_content_file,
    preview_content_columns,
)
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.tests.base import BaseTestCase


class ColumnsPreviewTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TEXT, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        self.spec = unit_spec_for(self.asset)

    def test_preview_content_columns_where_headers_match_aliases_should_auto_map_and_be_complete(self):
        # Arrange
        raw = b"id,sura,aya,translation\n1,1,1,In the name\n"

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.header_row, 1)
        self.assertEqual(preview.headers, ["id", "sura", "aya", "translation"])
        self.assertEqual(preview.mapping, {"surah": 1, "ayah": 2, "text": 3})
        self.assertEqual(preview.required, [["surah", "ayah", "text"]])
        self.assertTrue(preview.complete)

    def test_preview_content_columns_where_headers_unknown_should_list_headers_and_samples(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,In the name\n1,2,Praise\n\n1,3,x\n2,1,y\n"

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.headers, ["chapter", "verse", "meaning"])
        self.assertEqual(preview.mapping, {})
        self.assertFalse(preview.complete)
        self.assertEqual(preview.samples, [["1", "1", "In the name"], ["1", "2", "Praise"], ["1", "3", "x"]])
        self.assertEqual(preview.unit_fields, ["surah", "ayah"])

    def test_preview_content_columns_where_preamble_should_find_header_below_it(self):
        # Arrange
        raw = b'"Exported from QuranEnc\nline two"\nid,surah,ayah,meaning\n1,1,1,x\n'

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.header_row, 2)
        self.assertEqual(preview.mapping, {"surah": 1, "ayah": 2})

    def test_preview_content_columns_where_truncated_should_drop_the_cut_line(self):
        # Arrange
        raw = b"surah,ayah,text\n1,1,complete\n1,2,cut in the mid"

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=True)

        # Assert
        self.assertEqual(preview.samples, [["1", "1", "complete"]])

    def test_preview_content_columns_where_long_cells_should_cut_samples(self):
        # Arrange
        raw = b"surah,ayah,text\n1,1," + b"x" * PREVIEW_BYTES

        # Act
        preview = preview_content_columns(raw[:PREVIEW_BYTES], self.spec, ["text"], truncated=True)

        # Assert
        self.assertEqual(preview.headers, ["surah", "ayah", "text"])
        self.assertEqual(preview.samples, [])

    def test_preview_content_columns_where_data_cell_equals_an_alias_should_keep_the_real_header(self):
        # Arrange — "text" in the first data row is a text alias, but that row is data
        raw = b"chapter,verse,meaning\n1,1,text\n1,2,Praise\n"

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.header_row, 1)
        self.assertEqual(preview.headers, ["chapter", "verse", "meaning"])
        self.assertEqual(preview.samples, [["1", "1", "text"], ["1", "2", "Praise"]])

    def test_preview_content_columns_where_units_are_signed_or_arabic_indic_should_keep_the_real_header(self):
        # Arrange — int() reads "+1" and "١" as numbers, so these rows are data
        for raw in ("chapter,verse,meaning\n+1,+1,text\n1,2,Praise\n", "chapter,verse,meaning\n١,١,text\n1,2,Praise\n"):
            with self.subTest(raw=raw):
                # Act
                preview = preview_content_columns(raw.encode(), self.spec, ["text"], truncated=False)

                # Assert
                self.assertEqual(preview.header_row, 1)
                self.assertEqual(preview.headers, ["chapter", "verse", "meaning"])

    def test_preview_content_columns_where_ignored_only_alias_row_follows_data_should_keep_the_real_header(self):
        # Arrange — ",,,text" has no number, but it sits below the first data row
        raw = b"chapter,verse,meaning,notes\n1,1,First,\n,,,text\n1,2,Second,\n"

        # Act
        preview = preview_content_columns(raw, self.spec, ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.header_row, 1)
        self.assertEqual(preview.headers, ["chapter", "verse", "meaning", "notes"])

    def test_preview_content_columns_where_no_data_row_should_raise_parse_error(self):
        # Arrange — a header with nothing under it: there is no data to anchor the header to
        raw = b"chapter,verse,meaning\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            preview_content_columns(raw, self.spec, ["text"], truncated=False)

    def test_preview_content_columns_where_file_has_no_header_row_should_raise_parse_error(self):
        # Arrange
        raw = b"1,1,In the name\n1,2,Praise\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            preview_content_columns(raw, self.spec, ["text"], truncated=False)

    def test_preview_content_columns_where_word_template_should_offer_word_id_or_triple(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TEXT, template=AssetTemplateChoice.WORD, status=StatusChoice.READY
        )

        # Act
        preview = preview_content_columns(b"a,b,c\n1,1,x\n", unit_spec_for(asset), ["text"], truncated=False)

        # Assert
        self.assertEqual(preview.required, [["word_id", "text"], ["surah", "ayah", "word", "text"]])


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

    def test_parse_content_file_where_data_cell_equals_an_alias_should_import_every_row(self):
        # Arrange
        raw = b"chapter,verse,meaning\n1,1,text\n1,2,Praise\n"

        # Act
        parsed = parse_content_file(
            raw,
            self.spec,
            self.asset,
            column_keys=["text"],
            strict=True,
            column_mapping={"surah": 0, "ayah": 1, "text": 2},
        )

        # Assert
        self.assertEqual(
            [(p.unit_id, p.cells) for p in parsed],
            [(self.ayah1.id, {"text": "text"}), (self.ayah2.id, {"text": "Praise"})],
        )

    def test_parse_content_file_where_units_are_signed_should_import_every_row(self):
        # Arrange
        raw = b"chapter,verse,meaning\n+1,+1,text\n1,2,Praise\n"

        # Act
        parsed = parse_content_file(
            raw,
            self.spec,
            self.asset,
            column_keys=["text"],
            strict=True,
            column_mapping={"surah": 0, "ayah": 1, "text": 2},
        )

        # Assert
        self.assertEqual(
            [(p.unit_id, p.cells) for p in parsed],
            [(self.ayah1.id, {"text": "text"}), (self.ayah2.id, {"text": "Praise"})],
        )

    def test_parse_content_file_where_ignored_only_alias_row_follows_data_should_import_every_row(self):
        # Arrange
        raw = b"chapter,verse,meaning,notes\n1,1,First,\n,,,text\n1,2,Second,\n"

        # Act
        parsed = parse_content_file(
            raw,
            self.spec,
            self.asset,
            column_keys=["text"],
            strict=True,
            column_mapping={"surah": 0, "ayah": 1, "text": 2},
        )

        # Assert
        self.assertEqual(
            [(p.unit_id, p.cells) for p in parsed],
            [(self.ayah1.id, {"text": "First"}), (self.ayah2.id, {"text": "Second"})],
        )

    def test_parse_content_file_where_mapping_and_no_data_row_should_raise_parse_error(self):
        # Arrange
        raw = b"Exported\nchapter,verse,meaning\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(
                raw, self.spec, self.asset, column_keys=["text"], column_mapping={"surah": 0, "ayah": 1, "text": 2}
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

    def test_parse_content_file_where_ignored_column_has_text_on_a_blank_row_should_ignore_it(self):
        # Arrange — row 3 only has text in the ignored "notes" column
        raw = b"chapter,verse,meaning,notes\n1,1,x,\n,,,editor note\n"

        # Act
        parsed = parse_content_file(
            raw,
            self.spec,
            self.asset,
            column_keys=["text"],
            strict=True,
            column_mapping={"surah": 0, "ayah": 1, "text": 2},
        )

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.ayah1.id, {"text": "x"})])

    def test_parse_content_file_where_mapped_row_unreadable_should_report_its_file_row(self):
        # Arrange — row 3 has text in a mapped column but no surah
        raw = b"chapter,verse,meaning,notes\n1,1,x,\n,1,orphan,n\n"

        # Act / Assert
        with self.assertRaisesMessage(Exception, "{3: 'unreadable'}"):
            parse_content_file(
                raw,
                self.spec,
                self.asset,
                column_keys=["text"],
                strict=True,
                column_mapping={"surah": 0, "ayah": 1, "text": 2},
            )

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
