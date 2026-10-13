import importlib

from django.apps import apps as django_apps
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    StatusChoice,
)
from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
migration = importlib.import_module("apps.content.migrations.0006_assetversion_package_availability")


class BackfillFirstPublishedAtTests(BaseTestCase):
    def test_backfill_first_published_at_where_version_is_published_should_set_its_creation_time(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            status=StatusChoice.READY,
            language="ar",
        )
        fr = AssetLanguage.objects.create(asset=asset, language="fr", status=StatusChoice.READY)
        older = baker.make(AssetVersion, asset=asset, asset_language=fr, name="1.0")
        published = baker.make(AssetVersion, asset=asset, asset_language=fr, name="1.1")
        newer = baker.make(AssetVersion, asset=asset, asset_language=fr, name="1.2")
        AssetLanguage.objects.filter(pk=fr.pk).update(published_version=published)

        # Act
        migration.backfill_first_published_at(django_apps, None)

        # Assert
        for version in (older, published, newer):
            version.refresh_from_db()
        self.assertEqual(published.created_at, published.first_published_at)
        self.assertIsNone(older.first_published_at)
        self.assertIsNone(newer.first_published_at)
