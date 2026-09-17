from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    StatusChoice,
)
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class EntriesEnumerationTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def _draft_for(self, template, layout=None):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def test_list_entries_where_surah_asset_is_empty_should_return_baked_sura_rows(self):
        # Arrange — QuranDataMixin bakes 2 suras (see module docstring)
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 2)
        self.assertTrue(all(item["text"] == "" for item in body["results"]))
        self.assertEqual(AssetVersionEntry.objects.filter(version=version).count(), 0)

    def test_list_entries_where_surah_asset_has_one_entry_should_overlay_its_text(self):
        # Arrange
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        AssetVersionEntry.objects.create(version=version, sura_id=self.sura2.id, text="content", order=2)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        items = {item["unit_id"]: item["text"] for item in response.json()["results"]}
        self.assertEqual(items[self.sura2.id], "content")
        self.assertEqual(items[self.sura1.id], "")

    def test_list_entries_where_page_asset_should_return_layout_page_count_rows(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=5"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 604)
        self.assertEqual([item["unit_id"] for item in body["results"]], [1, 2, 3, 4, 5])
        self.assertEqual(body["results"][0]["unit_type"], "page")

    def test_list_entries_where_word_asset_filtered_by_sura_should_narrow_the_count(self):
        # Arrange — 2 words baked, both in sura 1 (see QuranDataMixin docstring)
        asset, version = self._draft_for(AssetTemplateChoice.WORD)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=10&sura=1"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertTrue(all(item["sura"] == 1 for item in body["results"]))

    def test_list_entries_where_ayah_asset_should_return_baked_ayah_rows(self):
        # Arrange — 3 ayahs baked, not the canonical 6236 (see QuranDataMixin docstring)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/?page_size=1"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["results"][0]["label"], "1:1")
