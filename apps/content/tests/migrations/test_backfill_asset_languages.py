from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice
from apps.content.services.asset_language_backfill import backfill_source_languages
from apps.core.tests.base import BaseTestCase


class BackfillSourceLanguagesTest(BaseTestCase):
    """Unit-tests the backfill helper used by migration 0056.

    Version-linking (setting ``asset_language`` on rows that lack one) cannot be
    reproduced through the ORM here because the column is now non-null (migration
    0057). That path is proven by the real migration: 0057's non-null alteration
    only succeeded because 0056 had already linked every existing version.
    """

    def test_creates_source_language_when_missing(self):
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")

        backfill_source_languages(Asset, AssetLanguage, AssetVersion)

        source = AssetLanguage.objects.get(asset=asset, is_source=True)
        self.assertEqual("ar", source.language)

    def test_promotes_existing_language_to_source(self):
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")
        AssetLanguage.objects.create(asset=asset, language="ar", is_source=False)

        backfill_source_languages(Asset, AssetLanguage, AssetVersion)

        source = AssetLanguage.objects.get(asset=asset, language="ar")
        self.assertTrue(source.is_source)

    def test_is_idempotent(self):
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")

        backfill_source_languages(Asset, AssetLanguage, AssetVersion)
        backfill_source_languages(Asset, AssetLanguage, AssetVersion)

        self.assertEqual(1, AssetLanguage.objects.filter(asset=asset).count())
