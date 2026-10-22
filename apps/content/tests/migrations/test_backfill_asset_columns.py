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
    CategoryChoice,
    VersionStateChoice,
)
from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0009_backfill_asset_columns")


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
