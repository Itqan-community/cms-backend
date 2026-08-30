from datetime import timedelta

from django.utils import timezone
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, AssetVersionEntry, CategoryChoice, StatusChoice, VersionStateChoice
from apps.content.tasks import cleanup_abandoned_content_drafts_task
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User


class AssetContentBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="French Rashid",
            slug="french-rashid",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        # A tiny corpus: sura 1 with 3 ayahs.
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayahs = [baker.make(Ayah, id=i, sura=self.sura, number_in_sura=i, text=f"ayah {i}") for i in (1, 2, 3)]


class GetOrCreateDraftTest(AssetContentBaseTest):
    def test_get_or_create_draft_where_no_draft_exists_should_create_one(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("draft", body["state"])
        self.assertEqual(
            1,
            AssetVersion.objects.filter(asset=self.translation, state=VersionStateChoice.DRAFT).count(),
        )

    def test_get_or_create_draft_where_draft_exists_should_return_same_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        existing = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(existing.id, response.json()["id"])
        self.assertEqual(
            1,
            AssetVersion.objects.filter(asset=self.translation, state=VersionStateChoice.DRAFT).count(),
        )

    def test_get_or_create_draft_where_published_exists_should_seed_entries(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        published = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=published, ayah=self.ayahs[0], text="hello")
        baker.make(AssetVersionEntry, version=published, ayah=self.ayahs[1], text="world")

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        draft = AssetVersion.objects.get(asset=self.translation, state=VersionStateChoice.DRAFT)
        self.assertEqual(2, draft.entries.count())

    def test_get_or_create_draft_where_draft_is_stale_should_rebuild_from_newer_version(self):
        # Arrange — an existing draft, then a NEWER published version (e.g. an upload)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        stale_draft = baker.make(AssetVersion, asset=self.translation, name="wip", state=VersionStateChoice.DRAFT)
        baker.make(AssetVersionEntry, version=stale_draft, ayah=self.ayahs[0], text="old draft text")
        newer = baker.make(AssetVersion, asset=self.translation, name="v2", state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=newer, ayah=self.ayahs[0], text="new uploaded text")
        # make the published version newer than the draft
        AssetVersion.objects.filter(pk=stale_draft.pk).update(created_at=timezone.now() - timedelta(hours=1))

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert — stale draft rebuilt; its content now reflects the newer version
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(AssetVersion.objects.filter(pk=stale_draft.pk).exists())
        draft = AssetVersion.objects.get(asset=self.translation, state=VersionStateChoice.DRAFT)
        self.assertEqual("new uploaded text", draft.entries.get(ayah_id=1).text)

    def test_get_or_create_draft_where_draft_newer_than_published_should_be_kept(self):
        # Arrange — a draft created AFTER the latest published version
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        published = baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=published.pk).update(created_at=timezone.now() - timedelta(hours=1))
        draft = baker.make(AssetVersion, asset=self.translation, name="wip", state=VersionStateChoice.DRAFT)

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert — the same (not-stale) draft is returned
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(draft.id, response.json()["id"])

    def test_get_or_create_draft_where_name_ends_with_number_should_increment_it(self):
        # Arrange — latest published version named "v1"
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert — draft is "v2", not "v1 (2)"
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("v2", response.json()["name"])

    def test_get_or_create_draft_where_v2_and_v3_exist_should_pick_next_free_number(self):
        # Arrange — v1 (latest), and v2/v3 already taken
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        older = baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(hours=2))
        for nm, ago in (("v2", 90), ("v3", 30)):
            v = baker.make(AssetVersion, asset=self.translation, name=nm, state=VersionStateChoice.PUBLISHED)
            AssetVersion.objects.filter(pk=v.pk).update(created_at=timezone.now() - timedelta(minutes=ago))

        # Act — latest is v3, so the draft should become v4
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("v4", response.json()["name"])

    def test_get_or_create_draft_where_name_has_no_number_should_append_counter(self):
        # Arrange — latest published named without any digits
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        baker.make(
            AssetVersion,
            asset=self.translation,
            name="First edition",
            state=VersionStateChoice.PUBLISHED,
        )

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("First edition 2", response.json()["name"])

    def test_get_or_create_draft_where_published_name_is_max_length_should_not_overflow(self):
        # Arrange — a published version whose name is exactly at the 255 limit
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        long_name = "n" * 255
        baker.make(
            AssetVersion,
            asset=self.translation,
            name=long_name,
            state=VersionStateChoice.PUBLISHED,
        )

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert — draft created with a unique name kept within max_length
        self.assertEqual(200, response.status_code, response.content)
        draft = AssetVersion.objects.get(asset=self.translation, state=VersionStateChoice.DRAFT)
        self.assertLessEqual(len(draft.name), 255)
        self.assertNotEqual(long_name, draft.name)

    def test_get_or_create_draft_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(f"/portal/content/translations/{self.translation.slug}/draft/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class PatchEntriesTest(AssetContentBaseTest):
    def _make_draft(self) -> AssetVersion:
        return baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)

    def test_patch_entries_where_new_rows_should_create_entries(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = self._make_draft()

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/entries/",
            data={
                "rows": [
                    {"ayah_id": 1, "text": "au nom", "footnotes": "[note]"},
                    {"ayah_id": 2, "text": "louange"},
                ]
            },
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, draft.entries.count())
        entry = draft.entries.get(ayah_id=1)
        self.assertEqual("au nom", entry.text)
        self.assertEqual("[note]", entry.footnotes)

    def test_patch_entries_where_existing_row_should_update_text(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = self._make_draft()
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="old")

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/entries/",
            data={"rows": [{"ayah_id": 1, "text": "new"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, draft.entries.count())
        self.assertEqual("new", draft.entries.get(ayah_id=1).text)

    def test_patch_entries_where_version_is_published_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        published = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{published.id}/entries/",
            data={"rows": [{"ayah_id": 1, "text": "x"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_editable", response.json()["error_name"])


class PublishDraftTest(AssetContentBaseTest):
    def test_publish_draft_where_valid_should_become_latest_published(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=True)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="text")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"name": "V2"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertEqual(VersionStateChoice.PUBLISHED, draft.state)
        self.assertEqual(draft.id, self.translation.get_latest_version().id)
        # publish name is persisted (not just held in memory)
        self.assertEqual("V2", draft.name)

    def test_publish_draft_where_no_changes_should_return_400(self):
        # Arrange — a seeded, unedited draft (content_edited stays False)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=False)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="seeded")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("no_changes_to_publish", response.json()["error_name"])

    def test_patch_entries_should_mark_draft_as_edited(self):
        # Arrange — a fresh, unedited draft
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=False)

        # Act — edit an entry
        response = self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/entries/",
            data={"rows": [{"ayah_id": 1, "text": "edited"}]},
            content_type="application/json",
        )

        # Assert — draft is now flagged as edited (so it can be published)
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertTrue(draft.content_edited)

    def test_publish_draft_should_generate_downloadable_file_from_entries(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(
            AssetVersion,
            asset=self.translation,
            name="v1",
            state=VersionStateChoice.DRAFT,
            file_url=None,
            content_edited=True,
        )
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="au nom", footnotes="[n]")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={},
            content_type="application/json",
        )

        # Assert — a CSV file now exists so consumer download works
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertTrue(bool(draft.file_url))
        draft.file_url.open("rb")
        content = draft.file_url.read().decode("utf-8")
        draft.file_url.close()
        self.assertIn("sura,aya,text,footnotes", content)
        self.assertIn("au nom", content)

    def test_publish_draft_where_not_a_draft_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        published = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{published.id}/publish/",
            data={},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_editable", response.json()["error_name"])


class DiscardDraftTest(AssetContentBaseTest):
    def test_discard_draft_where_valid_should_delete_draft_and_entries(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="x")

        # Act
        response = self.client.delete(f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(AssetVersion.objects.filter(id=draft.id).exists())
        self.assertEqual(0, AssetVersionEntry.objects.filter(version_id=draft.id).count())


class DraftExclusionTest(AssetContentBaseTest):
    def test_get_latest_version_where_only_draft_exists_should_return_none(self):
        # Arrange
        baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)

        # Act
        latest = self.translation.get_latest_version()

        # Assert
        self.assertIsNone(latest)

    def test_list_versions_where_draft_present_should_exclude_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        baker.make(AssetVersion, asset=self.translation, name="V1", state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersion, asset=self.translation, name="D", state=VersionStateChoice.DRAFT)

        # Act
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = [v["name"] for v in response.json()["results"]]
        self.assertEqual(["V1"], names)


class TafsirContentTest(AssetContentBaseTest):
    def setUp(self):
        super().setUp()
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tabari",
            slug="tabari",
        )

    def test_get_or_create_draft_where_tafsir_should_create_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        response = self.client.post(f"/portal/content/tafsirs/{self.tafsir.slug}/draft/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("draft", response.json()["state"])

    def test_get_or_create_draft_where_only_translation_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act — translation permission must NOT grant tafsir editing
        response = self.client.post(f"/portal/content/tafsirs/{self.tafsir.slug}/draft/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_get_or_create_draft_where_unsupported_category_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        response = self.client.post(f"/portal/content/recitations/{self.tafsir.slug}/draft/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("unsupported_content_category", response.json()["error_name"])


class VersionUploadImportTest(AssetContentBaseTest):
    def test_create_version_with_csv_file_should_import_entries_from_saved_file(self):
        # Arrange — a quranenc-style CSV upload (read back from the saved file, not
        # the consumed upload stream)
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.content.services.tafsir import TafsirService

        baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tabari",
            slug="tabari-import",
        )
        csv_bytes = b"sura,aya,text,footnotes\n" b"1,1,imported one,fn1\n" b"1,2,imported two,\n"
        upload = SimpleUploadedFile("t.csv", csv_bytes, content_type="text/csv")

        # Act
        version = TafsirService().create_tafsir_version(
            "tabari-import", name="v1", summary="", file=upload, publisher_q=None
        )

        # Assert — entries populated from the file content
        self.assertEqual(2, version.entries.count())
        self.assertEqual("imported one", version.entries.get(ayah_id=1).text)
        self.assertEqual("fn1", version.entries.get(ayah_id=1).footnotes)


class ExportVersionTest(AssetContentBaseTest):
    def test_export_where_version_has_entries_should_return_csv(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=version, ayah=self.ayahs[0], text="au nom", footnotes="[n]")

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version.id}/export/"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertIn("sura,aya,text,footnotes", body)
        self.assertIn("au nom", body)

    def test_export_where_version_name_is_arabic_should_encode_content_disposition(self):
        # Arrange — a version name with non-ASCII (Arabic) characters
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation, name="الإصدار ١", state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=version, ayah=self.ayahs[0], text="نص")

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version.id}/export/"
        )

        # Assert — header is valid latin-1 (RFC 5987 filename*), no UnicodeEncodeError
        self.assertEqual(200, response.status_code, response.content)
        disposition = response["Content-Disposition"]
        self.assertIn("attachment", disposition)
        self.assertIn("filename*=utf-8''", disposition)
        disposition.encode("latin-1")  # would raise if non-ASCII leaked in unencoded

    def test_export_where_no_entries_and_no_file_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation, name="empty", state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version.id}/export/"
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("version_not_found", response.json()["error_name"])

    def test_export_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        version = baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version.id}/export/"
        )

        # Assert
        self.assertEqual(403, response.status_code)


class CleanupAbandonedDraftsTaskTest(AssetContentBaseTest):
    def test_cleanup_where_draft_is_stale_should_delete_it(self):
        # Arrange — a stale draft WITH entries; the reported count must be the number
        # of draft versions, not the cascaded entry rows.
        stale = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)
        baker.make(AssetVersionEntry, version=stale, ayah=self.ayahs[0], text="x")
        baker.make(AssetVersionEntry, version=stale, ayah=self.ayahs[1], text="y")
        AssetVersion.objects.filter(pk=stale.pk).update(updated_at=timezone.now() - timedelta(hours=48))

        # Act
        result = cleanup_abandoned_content_drafts_task(older_than_hours=24)

        # Assert — 1 draft version deleted (not 3 = version + 2 entries)
        self.assertEqual(1, result["deleted"])
        self.assertFalse(AssetVersion.objects.filter(pk=stale.pk).exists())

    def test_cleanup_where_draft_is_recent_should_keep_it(self):
        # Arrange
        fresh = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT)

        # Act
        result = cleanup_abandoned_content_drafts_task(older_than_hours=24)

        # Assert
        self.assertEqual(0, result["deleted"])
        self.assertTrue(AssetVersion.objects.filter(pk=fresh.pk).exists())

    def test_cleanup_where_version_is_published_should_keep_it(self):
        # Arrange
        published = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=published.pk).update(updated_at=timezone.now() - timedelta(hours=48))

        # Act
        result = cleanup_abandoned_content_drafts_task(older_than_hours=24)

        # Assert
        self.assertEqual(0, result["deleted"])
        self.assertTrue(AssetVersion.objects.filter(pk=published.pk).exists())
