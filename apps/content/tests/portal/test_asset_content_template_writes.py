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
from apps.content.tests.quran_data import QuranDataMixin
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User

# The brief's literal test snippet calls `self.authenticate_user(permissions=[...])`,
# but `BaseTestCase.authenticate_user` takes a `User` positionally and has no
# `permissions` kwarg (it forwards unknown kwargs to `client.credentials` as HTTP
# headers). That would raise `TypeError: missing 1 required positional argument:
# 'user'`, so this file instead follows the working pattern used elsewhere in this
# suite (e.g. `apps/content/tests/portal/test_asset_content.py`): create a user,
# authenticate it, then grant permissions via `give_permission`. These freshly
# baked assets have no publisher membership set up, so the user also needs
# `PORTAL_ACCESS_ALL_LANGUAGES` to pass the per-version language gate
# (`require_version_language`) — without it every request 403s before reaching
# the behaviour under test.


class EntryWriteTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)

    def _draft_for(self, template):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT)
        return asset, version

    def test_patch_entries_where_surah_template_should_write_the_sura_column(self):
        # sura id 2 is baked by bake_quran; 999 below is deliberately absent
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 2, "text": "surah two"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.sura_id, 2)
        self.assertIsNone(entry.ayah_id)
        self.assertEqual(entry.text, "surah two")

    def test_patch_entries_where_page_template_should_write_the_page_no_column(self):
        # Arrange
        self.authenticate_user(self.user)
        layout = baker.make("content.MushafLayout", name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 7, "text": "page seven"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.page_no, 7)

    def test_patch_entries_where_unit_out_of_range_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 999, "text": "nope"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error_name"], "unit_not_in_template")

    def test_patch_entries_where_ayah_template_should_still_write_the_ayah_column(self):
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 1, "text": "bismillah"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.ayah_id, 1)
