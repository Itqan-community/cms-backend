from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.services.asset_columns import AssetColumnService
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class AssetColumnServiceTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        self.service = AssetColumnService()

    def test_create_column_where_asset_has_default_column_should_append_after_it(self):
        # Arrange
        self.asset.ensure_text_columns()

        # Act
        column = self.service.create_column(self.asset, key="answer", label_en="Answer", label_ar="الجواب")

        # Assert
        self.assertEqual(column.order, 1)
        self.assertEqual([c.key for c in self.asset.text_columns()], ["text", "answer"])
        self.assertEqual(column.label_ar, "الجواب")

    def test_create_column_where_key_taken_should_raise_column_key_taken(self):
        # Arrange
        self.asset.ensure_text_columns()

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.create_column(self.asset, key="text")

        # Assert
        self.assertEqual(raised.exception.error_name, "column_key_taken")

    def test_create_column_where_key_reserved_should_raise_column_key_invalid(self):
        # Arrange / Act
        with self.assertRaises(ItqanError) as raised:
            self.service.create_column(self.asset, key="ayah")

        # Assert
        self.assertEqual(raised.exception.error_name, "column_key_invalid")

    def test_update_column_where_uncommitted_should_change_key(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]

        # Act
        updated = self.service.update_column(column, key="question", label_en="Question")

        # Assert
        self.assertEqual(updated.key, "question")
        self.assertEqual(updated.label_en, "Question")

    def test_update_column_where_old_superseded_version_has_key_should_raise_column_committed(self):
        # Arrange — only an old, superseded commit still names the key
        column = self.asset.ensure_text_columns()[0]
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["text"], name="1.0")
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.update_column(column, key="question")

        # Assert
        self.assertEqual(raised.exception.error_name, "column_committed")

    def test_update_column_where_committed_should_still_allow_labels(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["text"])

        # Act
        updated = self.service.update_column(column, label_ar="النص")

        # Assert
        self.assertEqual(updated.label_ar, "النص")

    def test_delete_column_where_committed_should_raise_column_committed(self):
        # Arrange
        self.asset.ensure_text_columns()
        answer = self.service.create_column(self.asset, key="answer")
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.PUBLISHED, column_keys=["text", "answer"])

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.delete_column(answer)

        # Assert
        self.assertEqual(raised.exception.error_name, "column_committed")

    def test_delete_column_where_only_column_should_raise_column_last(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.delete_column(column)

        # Assert
        self.assertEqual(raised.exception.error_name, "column_last")

    def test_delete_column_where_uncommitted_should_remove_its_draft_cells(self):
        # Arrange
        self.asset.ensure_text_columns()
        answer = self.service.create_column(self.asset, key="answer")
        draft = baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)
        AssetVersionEntry.objects.create(version=draft, ayah=self.ayah1, column=answer, text="A")
        AssetVersionEntry.objects.create(version=draft, ayah=self.ayah1, text="T")

        # Act
        self.service.delete_column(answer)

        # Assert
        self.assertFalse(AssetColumn.objects.filter(pk=answer.pk).exists())
        self.assertEqual(list(draft.entries.values_list("text", flat=True)), ["T"])

    def test_reorder_columns_where_keys_match_should_reorder(self):
        # Arrange
        self.asset.ensure_text_columns()
        self.service.create_column(self.asset, key="answer")

        # Act
        columns = self.service.reorder_columns(self.asset, ["answer", "text"])

        # Assert
        self.assertEqual([c.key for c in columns], ["answer", "text"])
        self.assertEqual([c.key for c in self.asset.text_columns()], ["answer", "text"])

    def test_reorder_columns_where_key_set_differs_should_raise_column_order_mismatch(self):
        # Arrange
        self.asset.ensure_text_columns()
        self.service.create_column(self.asset, key="answer")

        # Act
        with self.assertRaises(ItqanError) as raised:
            self.service.reorder_columns(self.asset, ["answer"])

        # Assert
        self.assertEqual(raised.exception.error_name, "column_order_mismatch")

    def test_is_committed_where_only_draft_uses_column_should_be_false(self):
        # Arrange
        column = self.asset.ensure_text_columns()[0]
        baker.make(AssetVersion, asset=self.asset, state=VersionStateChoice.DRAFT)

        # Act / Assert
        self.assertFalse(self.service.is_committed(column))
