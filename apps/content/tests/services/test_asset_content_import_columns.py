from model_bakery import baker

from apps.content.models import Asset, AssetColumn, AssetTemplateChoice, CategoryChoice, StatusChoice
from apps.content.services.asset_content import AssetContentService
from apps.content.services.asset_content_import import (
    AssetContentInvalidRowsError,
    AssetContentMissingColumnsError,
    AssetContentParseError,
    parse_content_file,
)
from apps.content.services.asset_templates import unit_spec_for
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class MultiColumnImportTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        self.spec = unit_spec_for(self.asset)

    def test_parse_content_file_where_single_column_translation_header_should_parse_into_text(self):
        # Arrange
        raw = b"id,surah,ayah,translation\n1,1,1,In the name\n"

        # Act
        parsed = parse_content_file(raw, self.spec, self.asset, column_keys=["text"])

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.ayah1.id, {"text": "In the name"})])

    def test_parse_content_file_where_two_columns_should_parse_both_cells(self):
        # Arrange
        raw = b"surah,ayah,question,answer\n1,1,Q1,A1\n1,2,,A2\n2,1,,\n"

        # Act
        parsed = parse_content_file(raw, self.spec, self.asset, column_keys=["question", "answer"])

        # Assert
        self.assertEqual(
            [(p.unit_id, p.cells) for p in parsed],
            [(self.ayah1.id, {"question": "Q1", "answer": "A1"}), (self.ayah2.id, {"answer": "A2"})],
        )

    def test_parse_content_file_where_two_columns_and_one_missing_should_raise_missing_columns(self):
        # Arrange
        raw = b"surah,ayah,answer\n1,1,A1\n"

        # Act
        with self.assertRaises(AssetContentMissingColumnsError) as raised:
            parse_content_file(raw, self.spec, self.asset, column_keys=["question", "answer"])

        # Assert
        self.assertEqual(raised.exception.missing, ["question"])

    def test_parse_content_file_where_two_columns_should_not_accept_text_aliases(self):
        # Arrange
        raw = b"surah,ayah,translation,answer\n1,1,Q1,A1\n"

        # Act / Assert
        with self.assertRaises(AssetContentMissingColumnsError):
            parse_content_file(raw, self.spec, self.asset, column_keys=["question", "answer"])

    def test_parse_content_file_where_strict_and_duplicate_with_different_cells_should_flag_row(self):
        # Arrange
        raw = b"surah,ayah,question,answer\n1,1,Q,A\n1,1,Q,other\n"

        # Act
        with self.assertRaises(AssetContentInvalidRowsError) as raised:
            parse_content_file(raw, self.spec, self.asset, column_keys=["question", "answer"], strict=True)

        # Assert
        self.assertEqual(raised.exception.rows, {3: "duplicate"})

    def test_parse_content_file_where_word_template_two_columns_should_parse_by_word_id(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.WORD, status=StatusChoice.READY
        )
        raw = b"word_id,surah,ayah,word,question,answer\n2,1,1,2,Q,A\n"

        # Act
        parsed = parse_content_file(raw, unit_spec_for(asset), asset, column_keys=["question", "answer"])

        # Assert
        self.assertEqual([(p.unit_id, p.cells) for p in parsed], [(self.word2.id, {"question": "Q", "answer": "A"})])

    def test_parse_content_file_where_missing_columns_should_still_be_a_parse_error(self):
        # Arrange / Act / Assert — callers that catch the base error keep working
        self.assertTrue(issubclass(AssetContentMissingColumnsError, AssetContentParseError))

    def test_import_file_into_version_where_column_missing_should_raise_content_file_missing_columns(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        version = baker.make("content.AssetVersion", asset=self.asset)

        # Act
        with self.assertRaises(ItqanError) as raised:
            AssetContentService().import_file_into_version(version, b"surah,ayah,answer\n1,1,A\n")

        # Assert
        self.assertEqual(raised.exception.error_name, "content_file_missing_columns")
        self.assertEqual(raised.exception.extra, {"missing": ["question"]})

    def test_import_file_into_version_where_two_columns_should_store_both_cells(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        version = baker.make("content.AssetVersion", asset=self.asset)

        # Act
        AssetContentService().import_file_into_version(version, b"surah,ayah,question,answer\n1,1,Q,A\n")

        # Assert
        self.assertEqual(set(version.entries.values_list("column__key", "text")), {("question", "Q"), ("answer", "A")})
