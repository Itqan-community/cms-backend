from django.core.cache import cache
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.tests.group_quran_data import GroupQuranDataMixin
from apps.core.tests.base import BaseTestCase


class GroupFileStructureTests(GroupQuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.bake_group_quran()

    def test_asset_file_structure_where_ayah_group_tafsir_should_return_range_header_and_rows(self):
        # Arrange
        asset = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH_GROUP,
            status=StatusChoice.READY,
            language="ar",
            restricted_for_tenant=False,
        )
        rendition = asset.get_or_create_source_language()
        column = asset.ensure_text_columns()[0]
        version = baker.make(
            AssetVersion,
            asset=asset,
            asset_language=rendition,
            state=VersionStateChoice.PUBLISHED,
            column_keys=["text"],
            name="1.0",
        )
        for start, end, text in ((4, 5, "later"), (1, 3, "first")):
            AssetVersionEntry.objects.create(
                version=version, column=column, text=text, order=start, from_ayah_id=start, to_ayah_id=end
            )
        rendition.published_version = version
        rendition.status = StatusChoice.READY
        rendition.save()

        # Act
        response = self.client.get(f"/cms-api/assets/{asset.id}/file-structure/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["template"], "ayah_group")
        self.assertEqual(body["header"], ["from_surah", "from_ayah", "to_surah", "to_ayah", "text"])
        self.assertEqual(body["rows"], [["1", "1", "1", "3", "first"], ["2", "1", "2", "2", "later"]])
