import importlib
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.db import connection
from model_bakery import baker

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
from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0009_backfill_asset_columns")
require_migration = importlib.import_module("apps.content.migrations.0010_asset_columns_required")


class BackfillAssetColumnsTests(BaseTestCase):
    def _run(self) -> None:
        migration.backfill(django_apps, SimpleNamespace(connection=connection))

    def test_backfill_where_text_asset_has_no_column_should_create_text_column(self):
        # Arrange
        tafsir = baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH)
        mushaf = baker.make(Asset, category=CategoryChoice.MUSHAF)

        # Act
        self._run()

        # Assert
        self.assertEqual(list(AssetColumn.objects.filter(asset=tafsir).values_list("key", flat=True)), ["text"])
        self.assertFalse(AssetColumn.objects.filter(asset=mushaf).exists())

    def test_backfill_where_asset_already_has_columns_should_not_add_text(self):
        # Arrange
        tafsir = baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH)
        AssetColumn.objects.create(asset=tafsir, key="question", order=0)

        # Act
        self._run()

        # Assert
        self.assertEqual(list(AssetColumn.objects.filter(asset=tafsir).values_list("key", flat=True)), ["question"])

    def test_backfill_where_committed_version_has_no_keys_should_freeze_text(self):
        # Arrange
        tafsir = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)
        committed = baker.make(AssetVersion, asset=tafsir, state=VersionStateChoice.PUBLISHED)
        draft = baker.make(AssetVersion, asset=tafsir, state=VersionStateChoice.DRAFT)

        # Act
        self._run()

        # Assert
        committed.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(committed.column_keys, ["text"])
        self.assertEqual(draft.column_keys, [])


class RequireAssetColumnsMigrationTests(QuranDataMixin, BaseTestCase):
    def test_backfill_cells_where_update_left_fk_checks_pending_should_allow_altering_the_table(self):
        # Arrange — moving a cell to another column queues a deferred FK check, as the
        # catch-up backfill does for rows the previous release wrote mid-deploy
        self.bake_quran()
        tafsir = baker.make(Asset, category=CategoryChoice.TAFSIR, template=AssetTemplateChoice.AYAH)
        text = AssetColumn.objects.create(asset=tafsir, key="text", order=0)
        other = AssetColumn.objects.create(asset=tafsir, key="other", order=1)
        version = baker.make(AssetVersion, asset=tafsir)
        entry = AssetVersionEntry.objects.create(version=version, ayah=self.ayah1, column=text, text="x")
        with connection.cursor() as cursor:
            cursor.execute("UPDATE content_assetversionentry SET column_id = %s WHERE id = %s", [other.id, entry.id])

        # Act
        require_migration.backfill_cells(django_apps, connection.schema_editor())

        # Assert — 0010's schema changes can now run in the same transaction
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE content_assetversionentry ALTER COLUMN column_id SET NOT NULL")
