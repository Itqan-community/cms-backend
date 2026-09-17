from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, AssetVersion, AssetVersionChange, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura


class AssetVersionChangeModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH, language="ar"
        )
        self.version = baker.make(AssetVersion, asset=self.asset)
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="ayah 1")

    def test_unique_change_per_version_ayah(self):
        AssetVersionChange.objects.create(
            version=self.version, ayah=self.ayah, change_type="modified", old_text="a", new_text="b", order=1
        )
        with self.assertRaises(IntegrityError):
            AssetVersionChange.objects.create(
                version=self.version, ayah=self.ayah, change_type="added", old_text="", new_text="c", order=1
            )

    def test_related_name_changes(self):
        AssetVersionChange.objects.create(
            version=self.version, ayah=self.ayah, change_type="added", old_text="", new_text="x", order=1
        )
        self.assertEqual(1, self.version.changes.count())
