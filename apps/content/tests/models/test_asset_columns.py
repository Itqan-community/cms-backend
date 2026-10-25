from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.content.columns import csv_header, validate_column_key
from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    VersionStateChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class AssetColumnModelTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH)

    def test_text_columns_where_tafsir_has_none_should_read_default_without_saving(self):
        # Arrange — a fresh tafsir has no column rows

        # Act
        columns = self.asset.text_columns()

        # Assert
        self.assertEqual([column.key for column in columns], ["text"])
        self.assertFalse(AssetColumn.objects.filter(asset=self.asset).exists())

    def test_ensure_text_columns_where_tafsir_has_none_should_create_text_column_once(self):
        # Arrange — a fresh tafsir has no column rows

        # Act
        first = self.asset.ensure_text_columns()
        second = self.asset.ensure_text_columns()

        # Assert
        self.assertEqual([column.key for column in first], ["text"])
        self.assertEqual([column.pk for column in second], [first[0].pk])
        self.assertEqual(AssetColumn.objects.filter(asset=self.asset).count(), 1)

    def test_text_columns_where_mushaf_should_return_empty(self):
        # Arrange
        mushaf = baker.make(Asset, category=CategoryChoice.MUSHAF)

        # Act
        columns = mushaf.text_columns()

        # Assert
        self.assertEqual(columns, [])
        self.assertFalse(AssetColumn.objects.filter(asset=mushaf).exists())

    def test_text_columns_where_several_columns_should_return_them_in_order(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)

        # Act
        keys = [column.key for column in self.asset.text_columns()]

        # Assert
        self.assertEqual(keys, ["question", "answer"])

    def test_entry_save_where_column_missing_should_default_to_first_column(self):
        # Arrange
        version = baker.make(AssetVersion, asset=self.asset)

        # Act
        entry = AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, text="x")

        # Assert
        self.assertEqual(entry.column.key, "text")

    def test_resolved_column_keys_where_version_has_frozen_keys_should_return_them(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        version = baker.make(
            AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["question", "answer"]
        )
        AssetColumn.objects.create(asset=self.asset, key="extra", order=2)

        # Act
        keys = version.resolved_column_keys

        # Assert
        self.assertEqual(keys, ["question", "answer"])

    def test_resolved_column_keys_where_draft_should_follow_asset_columns(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        draft = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)

        # Act
        keys = draft.resolved_column_keys

        # Assert
        self.assertEqual(keys, ["question", "answer"])

    def test_entry_unique_where_same_unit_two_columns_should_allow_both(self):
        # Arrange
        question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1)
        version = baker.make(AssetVersion, asset=self.asset)

        # Act
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, column=question, text="Q")
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, column=answer, text="A")

        # Assert
        self.assertEqual(version.entries.count(), 2)

    def test_entry_unique_where_same_unit_same_column_should_raise_integrity_error(self):
        # Arrange
        question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        version = baker.make(AssetVersion, asset=self.asset)
        AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, column=question, text="Q")

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, column=question, text="again")

    def test_column_key_unique_where_duplicate_key_on_asset_should_raise_integrity_error(self):
        # Arrange
        AssetColumn.objects.create(asset=self.asset, key="question", order=0)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetColumn.objects.create(asset=self.asset, key="question", order=1)


class ColumnHelperTests(BaseTestCase):
    def test_csv_header_where_ayah_two_columns_should_append_keys(self):
        # Arrange / Act
        header = csv_header(AssetTemplateChoice.AYAH, ["question", "answer"])

        # Assert
        self.assertEqual(header, ["surah", "ayah", "question", "answer"])

    def test_csv_header_where_each_template_single_text_column_should_match_existing_headers(self):
        # Arrange / Act / Assert
        self.assertEqual(csv_header(AssetTemplateChoice.SURAH, ["text"]), ["sura", "text"])
        self.assertEqual(csv_header(AssetTemplateChoice.WORD, ["text"]), ["word_id", "sura", "aya", "word", "text"])
        self.assertEqual(csv_header(AssetTemplateChoice.PAGE, ["text"]), ["page", "text"])
        self.assertEqual(
            csv_header(AssetTemplateChoice.AYAH, ["text"], verbose=True),
            ["surah", "ayah", "surah_name", "ayah_text", "text"],
        )

    def test_validate_column_key_where_reserved_or_malformed_should_raise(self):
        # Arrange
        bad_keys = ["sura", "surah_name", "Question", "1a", "", "a" * 65, "with space"]

        for key in bad_keys:
            # Act
            with self.assertRaises(ItqanError) as raised:
                validate_column_key(key)

            # Assert
            self.assertEqual(raised.exception.error_name, "column_key_invalid", key)

    def test_validate_column_key_where_key_is_an_import_unit_alias_should_raise(self):
        # Arrange
        aliases = ["word_index", "position", "page_no", "word_id"]

        for key in aliases:
            # Act
            with self.assertRaises(ItqanError) as raised:
                validate_column_key(key)

            # Assert
            self.assertEqual(raised.exception.error_name, "column_key_invalid", key)

    def test_validate_column_key_where_key_is_not_plain_ascii_should_raise(self):
        # Arrange — Arabic, accented and full-width letters, and a trailing newline
        bad_keys = ["سؤال", "réponse", "ｑuestion", "text\n"]

        for key in bad_keys:
            # Act
            with self.assertRaises(ItqanError) as raised:
                validate_column_key(key)

            # Assert
            self.assertEqual(raised.exception.error_name, "column_key_invalid", repr(key))

    def test_validate_column_key_where_valid_should_not_raise(self):
        # Arrange / Act / Assert
        for key in ["text", "question", "wrong_answer_1", "a"]:
            validate_column_key(key)
