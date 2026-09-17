from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
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

    def test_patch_entries_where_word_template_should_write_the_word_column(self):
        # word id 1 is baked by bake_quran (word1: sura 1, ayah 1, position 1, text "w1")
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.WORD)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 1, "text": "word one gloss"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.word_id, 1)
        row = response.json()[0]
        self.assertEqual("1:1:1", row["label"])
        self.assertEqual("w1", row["reference_text"])

    def test_pending_diff_where_surah_template_should_label_the_unit(self):
        # sura id 2 is baked by bake_quran as "Al-Baqara"
        # Arrange
        self.authenticate_user(self.user)
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        self.client.patch(
            f"/portal/content/translations/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 2, "text": "cow"}]},
            content_type="application/json",
        )

        # Act
        response = self.client.get(f"/portal/content/translations/{asset.slug}/versions/{version.id}/pending-diff/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        row = response.json()["results"][0]
        self.assertEqual("surah", row["unit_type"])
        self.assertEqual(2, row["unit_id"])
        self.assertEqual("2. Al-Baqara", row["label"])

    def test_get_or_create_draft_where_surah_template_translation_should_not_seed_mushaf_rows(self):
        # Regression guard: `ensure_mushaf_coverage` / the `mushaf_version` seed
        # path only applies to the ayah template. A published source (ar) version
        # here carries surah-keyed entries, so if the guard ever regressed, the
        # draft-seeding code would try to read `entry.ayah_id` off those rows
        # (always None for a surah-keyed entry) and either seed a garbage empty
        # unit or raise IntegrityError on the exactly-one-unit constraint. The
        # correct, guarded behaviour is a plain empty draft: no "es" version
        # exists yet to copy from, and no mushaf overlay applies to this template.
        # Arrange
        self.authenticate_user(self.user)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.SURAH,
        )
        ar_lang = asset.get_or_create_source_language()
        ar_version = baker.make(AssetVersion, asset=asset, asset_language=ar_lang, state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=ar_version, sura=self.sura1, text="sura one", order=1)
        AssetLanguage.objects.create(asset=asset, language="es")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{asset.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        draft = AssetVersion.objects.get(id=response.json()["id"])
        self.assertEqual(0, draft.entries.count())
