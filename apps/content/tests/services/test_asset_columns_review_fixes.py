"""Fixes from the final review: upload commits freeze columns, assets stay deletable."""

from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetColumn,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.services.asset_columns import AssetColumnService
from apps.content.services.tafsir import TafsirService
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class UploadCommitColumnTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        self.question = AssetColumn.objects.create(asset=self.asset, key="question", order=0)
        self.answer = AssetColumn.objects.create(asset=self.asset, key="answer", order=1)

    def _upload(self, content: str, *, version_number: str | None = "1.0", bump: str = "minor") -> AssetVersion:
        return TafsirService().create_tafsir_version(
            self.asset.slug,
            file=SimpleUploadedFile("qa.csv", content.encode()),
            version_number=version_number,
            bump=bump,
        )

    def test_create_tafsir_version_where_file_uploaded_should_freeze_column_keys(self):
        # Arrange / Act
        version = self._upload("surah,ayah,question,answer\n1,1,Q,\n")

        # Assert
        version.refresh_from_db()
        self.assertEqual(version.column_keys, ["question", "answer"])

    def test_create_tafsir_version_where_upload_had_blank_column_should_lock_that_column(self):
        # Arrange
        self._upload("surah,ayah,question,answer\n1,1,Q,\n")

        # Act
        with self.assertRaises(ItqanError) as raised:
            AssetColumnService().delete_column(self.answer)

        # Assert
        self.assertEqual(raised.exception.error_name, "column_committed")

    def test_create_tafsir_version_where_columns_reordered_after_upload_and_minor_should_raise(self):
        # Arrange
        self._upload("surah,ayah,question,answer\n1,1,Q,A\n")
        AssetColumnService().reorder_columns(self.asset, ["answer", "question"])

        # Act
        with self.assertRaises(ItqanError) as raised:
            self._upload("surah,ayah,question,answer\n1,1,Q2,A\n", version_number=None)

        # Assert
        self.assertEqual(raised.exception.error_name, "major_bump_required")

    def test_resolved_column_keys_where_uploaded_version_then_column_added_should_keep_upload_layout(self):
        # Arrange
        version = self._upload("surah,ayah,question,answer\n1,1,Q,A\n")

        # Act
        AssetColumn.objects.create(asset=self.asset, key="extra", order=2)

        # Assert
        version.refresh_from_db()
        self.assertEqual(version.resolved_column_keys, ["question", "answer"])


class AssetDeletionTests(QuranDataMixin, BaseTestCase):
    def test_delete_where_version_has_changes_should_delete_its_changes_and_keep_the_column(self):
        # Arrange — deleting a whole versioned asset is refused by AssetVersion.asset_language
        # (PROTECT, as on staging); the column FK must not add a blocker of its own.
        self.bake_quran()
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        change = AssetVersionChange.objects.create(version=version, ayah=self.ayah1, change_type="added", new_text="x")

        # Act
        version.delete()

        # Assert
        self.assertFalse(AssetVersionChange.objects.filter(pk=change.pk).exists())
        self.assertTrue(AssetColumn.objects.filter(pk=change.column_id).exists())

    def test_delete_where_text_asset_has_columns_and_no_versions_should_delete_its_columns(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        asset.ensure_text_columns()

        # Act
        asset.delete()

        # Assert
        self.assertFalse(AssetColumn.objects.filter(asset_id=asset.pk).exists())

    def test_delete_where_column_alone_has_changes_should_be_refused_by_the_database(self):
        # Arrange
        from django.db.models import RestrictedError

        self.bake_quran()
        asset = baker.make(
            Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH, status=StatusChoice.READY
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.PUBLISHED)
        change = AssetVersionChange.objects.create(version=version, ayah=self.ayah1, change_type="added", new_text="x")

        # Act / Assert
        with self.assertRaises(RestrictedError):
            change.column.delete()


class ReservedColumnKeyTests(BaseTestCase):
    def test_validate_column_key_where_order_should_raise_column_key_invalid(self):
        # Arrange
        from apps.content.columns import validate_column_key

        # Act
        with self.assertRaises(ItqanError) as raised:
            validate_column_key("order")

        # Assert
        self.assertEqual(raised.exception.error_name, "column_key_invalid")
