from datetime import timedelta

from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
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
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="French Rashid",
            slug="french-rashid",
            language="ar",
        )
        self.user = User.objects.create_user(email="editor@example.com", name="Editor", is_staff=True)
        # These suites exercise editing, not language assignment: give the user the
        # assignment bypass so they behave like the existing editor groups that the
        # rollout migration grants it to. Assignment itself is covered by its own tests.
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        # A tiny corpus: sura 1 with 3 ayahs.
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayahs = [baker.make(Ayah, id=i, sura=self.sura, number_in_sura=i, text=f"ayah {i}") for i in (1, 2, 3)]


class GetOrCreateDraftTest(AssetContentBaseTest):
    def test_get_or_create_draft_where_no_draft_exists_should_create_one(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert — the same (not-stale) draft is returned
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(draft.id, response.json()["id"])

    def test_get_or_create_draft_where_name_ends_with_number_should_increment_it(self):
        # Arrange — latest published version named "v1"
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert — draft created with a unique name kept within max_length
        self.assertEqual(200, response.status_code, response.content)
        draft = AssetVersion.objects.get(asset=self.translation, state=VersionStateChoice.DRAFT)
        self.assertLessEqual(len(draft.name), 255)
        self.assertNotEqual(long_name, draft.name)

    def test_get_or_create_draft_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
                    {"ayah_id": 1, "text": "au nom"},
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


class SourceReferenceEntriesTest(AssetContentBaseTest):
    def _publish_source_and_add_es(self):
        """Publish an ar (source) version with entries, then add an 'es' language."""
        ar_lang = self.translation.get_or_create_source_language()
        ar_version = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar_lang, state=VersionStateChoice.PUBLISHED
        )
        baker.make(AssetVersionEntry, version=ar_version, ayah=self.ayahs[0], text="source one", order=1)
        baker.make(AssetVersionEntry, version=ar_version, ayah=self.ayahs[1], text="source two", order=2)
        return AssetLanguage.objects.create(asset=self.translation, language="es")

    def _entries(self, version_id):
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version_id}/entries/"
        )
        self.assertEqual(200, response.status_code, response.content)
        return {row["ayah_id"]: row for row in response.json()["results"]}

    def test_translation_draft_is_seeded_with_source_ayahs_and_source_text(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self._publish_source_and_add_es()

        # Act — open the es draft
        draft_resp = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )
        draft_id = draft_resp.json()["id"]
        rows = self._entries(draft_id)

        # Assert — every source ayah shows, target empty, source_text populated
        self.assertEqual("source one", rows[self.ayahs[0].id]["source_text"])
        self.assertEqual("", rows[self.ayahs[0].id]["text"])
        self.assertEqual("source two", rows[self.ayahs[1].id]["source_text"])

    def test_source_language_entries_have_no_source_text(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self._publish_source_and_add_es()

        # Act — open the ar (source) draft
        draft_resp = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )
        rows = self._entries(draft_resp.json()["id"])

        # Assert — editing the source shows no reference column data
        self.assertIsNone(rows[self.ayahs[0].id]["source_text"])

    def test_publish_translation_drops_untouched_empty_rows(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self._publish_source_and_add_es()
        draft_resp = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )
        draft_id = draft_resp.json()["id"]
        # Translate only the first ayah, leaving the second empty.
        self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft_id}/entries/",
            data={"rows": [{"ayah_id": self.ayahs[0].id, "text": "traduccion uno"}]},
            content_type="application/json",
        )

        # Act
        publish = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft_id}/publish/",
            data={"message": "commit"},
            content_type="application/json",
        )

        # Assert — only the filled ayah persists (sparse coverage)
        self.assertEqual(200, publish.status_code, publish.content)
        published = AssetVersion.objects.get(id=draft_id)
        self.assertEqual(["traduccion uno"], list(published.entries.values_list("text", flat=True)))

    def test_reopen_translation_after_sparse_publish_shows_full_mushaf(self):
        # Regression: after a sparse translation publish (only ayah 1), re-opening
        # the editor must still show EVERY source ayah, not just the published one.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        self._publish_source_and_add_es()  # ar source covers ayahs 1 & 2; es added

        # Translate only ayah 1, then publish (ayah 2 dropped as empty).
        first = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )
        first_id = first.json()["id"]
        self.client.patch(
            f"/portal/content/translations/{self.translation.slug}/versions/{first_id}/entries/",
            data={"rows": [{"ayah_id": self.ayahs[0].id, "text": "uno"}]},
            content_type="application/json",
        )
        self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{first_id}/publish/",
            data={"message": "commit"},
            content_type="application/json",
        )

        # Re-open the es draft and read its rows.
        second = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )
        rows = self._entries(second.json()["id"])

        # Both source ayahs are present again (full mushaf), with source text.
        self.assertIn(self.ayahs[0].id, rows)
        self.assertIn(self.ayahs[1].id, rows)
        self.assertEqual("uno", rows[self.ayahs[0].id]["text"])
        self.assertEqual("", rows[self.ayahs[1].id]["text"])
        self.assertEqual("source two", rows[self.ayahs[1].id]["source_text"])

    def test_reopen_existing_sparse_translation_draft_tops_up_full_mushaf(self):
        # Regression: an already-existing sparse draft (e.g. from an upload or a
        # pre-fix open) must be topped up to the full mushaf when reopened, without
        # losing its in-progress edits.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        es_lang = self._publish_source_and_add_es()  # ar covers ayahs 1 & 2
        # An existing es draft that only covers ayah 1 (sparse).
        draft = baker.make(AssetVersion, asset=self.translation, asset_language=es_lang, state=VersionStateChoice.DRAFT)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="uno", order=1)

        # Act — reopen the es draft
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/draft/",
            data={"language": "es"},
            content_type="application/json",
        )

        # Assert — same draft, now topped up to cover every source ayah
        self.assertEqual(draft.id, response.json()["id"])
        rows = self._entries(draft.id)
        self.assertIn(self.ayahs[1].id, rows)
        self.assertEqual("uno", rows[self.ayahs[0].id]["text"])  # edit preserved
        self.assertEqual("", rows[self.ayahs[1].id]["text"])
        self.assertEqual("source two", rows[self.ayahs[1].id]["source_text"])


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
            data={"message": "first commit"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertEqual(VersionStateChoice.PUBLISHED, draft.state)
        self.assertEqual(draft.id, self.translation.get_latest_version().id)
        # the commit message is persisted as the version description
        self.assertEqual("first commit", draft.summary)

    def test_commit_records_delta_and_prunes_previous_head(self):
        # Arrange — a head (with a stored delta so the prune rule applies) + a draft
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        head = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED
        )
        baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="old one", order=1)
        baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[1], text="two", order=2)
        baker.make(
            AssetVersionChange, version=head, ayah=self.ayahs[0], change_type="added", new_text="old one", order=1
        )
        draft = baker.make(
            AssetVersion,
            asset=self.translation,
            asset_language=ar,
            name="v2",
            state=VersionStateChoice.DRAFT,
            content_edited=True,
        )
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="new one", order=1)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[1], text="two", order=2)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[2], text="three", order=3)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"message": "tweak ayah 1, add ayah 3"},
            content_type="application/json",
        )

        # Assert — delta recorded (unchanged ayah excluded), previous head pruned
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertEqual("tweak ayah 1, add ayah 3", draft.summary)
        changes = {c.ayah_id: c.change_type for c in draft.changes.all()}
        self.assertEqual("modified", changes[self.ayahs[0].id])
        self.assertEqual("added", changes[self.ayahs[2].id])
        self.assertNotIn(self.ayahs[1].id, changes)
        self.assertEqual(0, head.entries.count())

    def test_commit_requires_message(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=True)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="x")

        # Act — blank message
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"message": "   "},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("commit_message_required", response.json()["error_name"])

    def test_publish_draft_where_no_changes_should_return_400(self):
        # Arrange — a seeded, unedited draft (content_edited stays False)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=False)
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="seeded")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"message": "commit"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("no_changes_to_publish", response.json()["error_name"])

    def test_publish_draft_where_edited_but_matches_head_should_return_400(self):
        # Arrange — an edited draft whose final content equals the head (edit then
        # revert): content_edited is True, but the computed delta is empty.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        head = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED
        )
        baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="same", order=1)
        draft = baker.make(
            AssetVersion,
            asset=self.translation,
            asset_language=ar,
            name="v2",
            state=VersionStateChoice.DRAFT,
            content_edited=True,
        )
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="same", order=1)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"message": "no-op"},
            content_type="application/json",
        )

        # Assert — rejected, and the draft is preserved (transaction rolled back)
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("no_changes_to_publish", response.json()["error_name"])
        draft.refresh_from_db()
        self.assertEqual(VersionStateChoice.DRAFT, draft.state)
        self.assertEqual(1, draft.entries.count())

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

    def test_restore_version_makes_it_the_active_version(self):
        # Arrange — an older v1 and a newer v2 (both published, source language)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        old = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED
        )
        baker.make(AssetVersionEntry, version=old, ayah=self.ayahs[0], text="old text")
        baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v2", state=VersionStateChoice.PUBLISHED
        )
        AssetVersion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=1))

        # Act — restore the older v1
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{old.id}/restore/",
            data={},
            content_type="application/json",
        )

        # Assert — a new version becomes active with v1's content; original kept
        self.assertEqual(200, response.status_code, response.content)
        restored_id = response.json()["id"]
        self.assertNotEqual(old.id, restored_id)
        latest = self.translation.get_latest_version("ar")
        self.assertEqual(restored_id, latest.id)
        self.assertEqual("old text", latest.entries.get(ayah_id=self.ayahs[0].id).text)
        self.assertTrue(AssetVersion.objects.filter(pk=old.pk).exists())

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
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="au nom")

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
            data={"message": "commit"},
            content_type="application/json",
        )

        # Assert — a CSV file now exists so consumer download works
        self.assertEqual(200, response.status_code, response.content)
        draft.refresh_from_db()
        self.assertTrue(bool(draft.file_url))
        draft.file_url.open("rb")
        content = draft.file_url.read().decode("utf-8")
        draft.file_url.close()
        self.assertIn("surah,ayah,text", content)
        self.assertIn("au nom", content)

    def test_publish_draft_where_not_a_draft_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        published = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)

        # Act
        response = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{published.id}/publish/",
            data={"message": "commit"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_editable", response.json()["error_name"])


class VersionDiffTest(AssetContentBaseTest):
    def test_diff_returns_stored_changes(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        v = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)
        baker.make(
            AssetVersionChange,
            version=v,
            ayah=self.ayahs[0],
            change_type="modified",
            old_text="a",
            new_text="b",
            order=1,
        )

        resp = self.client.get(f"/portal/content/translations/{self.translation.slug}/versions/{v.id}/diff/")

        self.assertEqual(200, resp.status_code, resp.content)
        row = resp.json()["results"][0]
        self.assertEqual("modified", row["change_type"])
        self.assertEqual("a", row["old_text"])
        self.assertEqual("b", row["new_text"])
        self.assertEqual(1, row["aya"])

    def test_diff_computed_for_legacy_commit(self):
        # Legacy: no stored changes, full entries on both versions.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        old = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=1))
        baker.make(AssetVersionEntry, version=old, ayah=self.ayahs[0], text="a")
        new = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=new, ayah=self.ayahs[0], text="b")

        resp = self.client.get(f"/portal/content/translations/{self.translation.slug}/versions/{new.id}/diff/")

        self.assertEqual(200, resp.status_code, resp.content)
        row = resp.json()["results"][0]
        self.assertEqual("modified", row["change_type"])
        self.assertEqual("a", row["old_text"])
        self.assertEqual("b", row["new_text"])


class PendingDiffTest(AssetContentBaseTest):
    def test_pending_diff_shows_uncommitted_changes_vs_head(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        head = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=head.pk).update(created_at=timezone.now() - timedelta(hours=1))
        baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="old one")
        # draft: modify ayah 1, add ayah 2, plus an empty seeded row (ignored)
        draft = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.DRAFT, content_edited=True
        )
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="new one")
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[1], text="two")
        baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[2], text="")

        resp = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/pending-diff/"
        )

        self.assertEqual(200, resp.status_code, resp.content)
        changes = {r["ayah_id"]: r["change_type"] for r in resp.json()["results"]}
        self.assertEqual("modified", changes[self.ayahs[0].id])
        self.assertEqual("added", changes[self.ayahs[1].id])
        self.assertNotIn(self.ayahs[2].id, changes)  # empty seeded row excluded


class ReconstructAndRestoreTest(AssetContentBaseTest):
    def test_reconstruct_folds_deltas(self):
        ar = self.translation.get_or_create_source_language()
        # c1: snapshot anchor (has entries)
        c1 = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=c1.pk).update(created_at=timezone.now() - timedelta(hours=2))
        baker.make(AssetVersionEntry, version=c1, ayah=self.ayahs[0], text="one")
        # c2: delta-only (pruned form) — modify ayah1, add ayah2
        c2 = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
        AssetVersion.objects.filter(pk=c2.pk).update(created_at=timezone.now() - timedelta(hours=1))
        baker.make(
            AssetVersionChange,
            version=c2,
            ayah=self.ayahs[0],
            change_type="modified",
            old_text="one",
            new_text="ONE",
            order=1,
        )
        baker.make(AssetVersionChange, version=c2, ayah=self.ayahs[1], change_type="added", new_text="two", order=2)

        from apps.content.repositories.asset_content import AssetContentRepository

        state = AssetContentRepository().reconstruct_entries(c2)
        self.assertEqual({self.ayahs[0].id: "ONE", self.ayahs[1].id: "two"}, state)

    def test_restore_reconstructs_pruned_version(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        # pruned old commit represented only by deltas
        old = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED
        )
        AssetVersion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=2))
        baker.make(
            AssetVersionChange, version=old, ayah=self.ayahs[0], change_type="added", new_text="old text", order=1
        )
        head = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v2", state=VersionStateChoice.PUBLISHED
        )
        baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="head text")

        resp = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{old.id}/restore/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(200, resp.status_code, resp.content)
        latest = self.translation.get_latest_version("ar")
        self.assertEqual("old text", latest.entries.get(ayah_id=self.ayahs[0].id).text)

    def test_restore_legacy_file_only_version_materializes_entries(self):
        # A legacy commit that only has a stored file (no per-ayah entries and no
        # stored deltas) must be parsed and materialized into entries on restore,
        # not merely file-copied — otherwise the new head reads as empty.
        from django.core.files.base import ContentFile

        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        ar = self.translation.get_or_create_source_language()
        legacy = baker.make(
            AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED
        )
        legacy.file_url.save("legacy.csv", ContentFile(b"surah,ayah,text\n1,1,from file\n1,2,second"), save=True)

        resp = self.client.post(
            f"/portal/content/translations/{self.translation.slug}/versions/{legacy.id}/restore/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(200, resp.status_code, resp.content)
        latest = self.translation.get_latest_version("ar")
        self.assertNotEqual(legacy.id, latest.id)
        self.assertEqual("from file", latest.entries.get(ayah_id=self.ayahs[0].id).text)
        self.assertEqual("second", latest.entries.get(ayah_id=self.ayahs[1].id).text)
        # The restore records a delta like any other commit (all added here).
        self.assertTrue(latest.changes.exists())


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
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tabari",
            slug="tabari",
            language="ar",
        )

    def test_get_or_create_draft_where_tafsir_should_create_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        response = self.client.post(
            f"/portal/content/tafsirs/{self.tafsir.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("draft", response.json()["state"])

    def test_get_or_create_draft_where_only_translation_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act — translation permission must NOT grant tafsir editing
        response = self.client.post(
            f"/portal/content/tafsirs/{self.tafsir.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_get_or_create_draft_where_unsupported_category_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        response = self.client.post(
            f"/portal/content/recitations/{self.tafsir.slug}/draft/",
            data={"language": "ar"},
            content_type="application/json",
        )

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
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tabari",
            slug="tabari-import",
        )
        csv_bytes = b"sura,aya,text\n1,1,imported one\n1,2,imported two\n"
        upload = SimpleUploadedFile("t.csv", csv_bytes, content_type="text/csv")

        # Act
        version = TafsirService().create_tafsir_version(
            "tabari-import", name="v1", summary="", file=upload, publisher_q=None
        )

        # Assert — entries populated from the file content
        self.assertEqual(2, version.entries.count())
        self.assertEqual("imported one", version.entries.get(ayah_id=1).text)


class ExportVersionTest(AssetContentBaseTest):
    def test_export_where_version_has_entries_should_return_csv(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation, name="v1", state=VersionStateChoice.PUBLISHED)
        baker.make(AssetVersionEntry, version=version, ayah=self.ayahs[0], text="au nom")

        # Act
        response = self.client.get(
            f"/portal/content/translations/{self.translation.slug}/versions/{version.id}/export/"
        )

        # Assert — verbose columns help reviewers verify against the original
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertIn("surah,ayah,surah_name,ayah_text,text", body)
        self.assertIn("au nom", body)  # the entry text
        self.assertIn("الفاتحة", body)  # surah name
        self.assertIn("ayah 1", body)  # the original ayah text
        # Filename is {english name}-{language}-{version}.csv (whitespace → underscores)
        self.assertIn("French_Rashid-ar-v1.csv", response["Content-Disposition"])

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
