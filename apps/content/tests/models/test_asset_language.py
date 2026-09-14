from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice, VersionStateChoice
from apps.core.tests.base import BaseTestCase


class AssetLanguageModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")

    def test_unique_language_per_asset(self):
        AssetLanguage.objects.create(asset=self.asset, language="es")
        with self.assertRaises(IntegrityError):
            AssetLanguage.objects.create(asset=self.asset, language="es")

    def test_only_one_source_per_asset(self):
        AssetLanguage.objects.create(asset=self.asset, language="ar", is_source=True)
        with self.assertRaises(IntegrityError):
            AssetLanguage.objects.create(asset=self.asset, language="es", is_source=True)


class GetLatestVersionByLanguageTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")
        self.ar = AssetLanguage.objects.create(asset=self.asset, language="ar", is_source=True)
        self.es = AssetLanguage.objects.create(asset=self.asset, language="es")

    def test_get_latest_version_filters_by_language(self):
        v_ar = baker.make(AssetVersion, asset=self.asset, asset_language=self.ar, state=VersionStateChoice.PUBLISHED)
        v_es = baker.make(AssetVersion, asset=self.asset, asset_language=self.es, state=VersionStateChoice.PUBLISHED)

        self.assertEqual(v_es.id, self.asset.get_latest_version("es").id)
        self.assertEqual(v_ar.id, self.asset.get_latest_version("ar").id)
        # No language -> falls back to the asset's source language (ar).
        self.assertEqual(v_ar.id, self.asset.get_latest_version().id)
