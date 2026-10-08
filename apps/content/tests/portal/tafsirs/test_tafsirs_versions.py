from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionChangeReview,
    AssetVersionEntry,
    CategoryChoice,
    ReviewStateChoice,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User

# A file that parses into entries: uploads must, so their content can be reviewed.
CSV = b"surah,ayah,text\n1,1,in the name"


class TafsirVersionBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tafsir Al-Tabari",
            slug="tafsir-al-tabari",
        )
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)
        # These suites exercise editing, not language assignment: give the user the
        # assignment bypass so they behave like the existing editor groups that the
        # rollout migration grants it to. Assignment itself is covered by its own tests.
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")


class TafsirVersionListTest(TafsirVersionBaseTest):
    def test_list_versions_where_valid_slug_should_return_versions(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        baker.make(AssetVersion, asset=self.tafsir, name="V1")
        baker.make(AssetVersion, asset=self.tafsir, name="V2")

        # Act
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(2, len(body["results"]))
        self.assertEqual("V2", body["results"][0]["name"])  # Ordered by -created_at

    def test_list_versions_filtered_by_language(self):
        # Arrange — one source-language version and one French version
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        source = self.tafsir.get_or_create_source_language()
        fr = AssetLanguage.objects.create(asset=self.tafsir, language="fr")
        baker.make(AssetVersion, asset=self.tafsir, asset_language=source, name="SRC1")
        baker.make(AssetVersion, asset=self.tafsir, asset_language=fr, name="FR1")

        # Act
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/?language=fr")

        # Assert — only the French version, and each row exposes its language
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body["results"]))
        self.assertEqual("FR1", body["results"][0]["name"])
        self.assertEqual("fr", body["results"][0]["language"])

    def test_list_versions_by_source_language_includes_legacy_null_language_versions(self):
        # Legacy rows predate multi-language and can carry a null asset_language;
        # they belong to the source language and must appear when it is filtered.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        source = self.tafsir.get_or_create_source_language()
        baker.make(AssetVersion, asset=self.tafsir, asset_language=source, name="SRC1")
        legacy = baker.make(AssetVersion, asset=self.tafsir, name="LEGACY")
        AssetVersion.objects.filter(pk=legacy.pk).update(asset_language=None)

        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/?language={self.tafsir.language}")

        self.assertEqual(200, response.status_code, response.content)
        names = {row["name"] for row in response.json()["results"]}
        self.assertIn("SRC1", names)
        self.assertIn("LEGACY", names)

    def test_list_versions_exposes_author_and_change_counts(self):
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        version = baker.make(AssetVersion, asset=self.tafsir, name="v1", created_by=self.user)
        baker.make(AssetVersionChange, version=version, ayah=self.ayah, change_type="added", new_text="x", order=1)

        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")

        self.assertEqual(200, response.status_code, response.content)
        row = response.json()["results"][0]
        self.assertEqual("Test User", row["created_by"])
        self.assertEqual({"added": 1, "modified": 0, "removed": 0}, row["change_counts"])

    def test_list_versions_where_tafsir_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)

        # Act
        response = self.client.get("/portal/tafsirs/non-existent/versions/")

        # Assert
        self.assertEqual(404, response.status_code)

    def test_list_versions_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")
        self.assertEqual(401, response.status_code)

    def test_list_versions_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TafsirVersionCreateTest(TafsirVersionBaseTest):
    def test_create_version_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={
                "asset_id": self.tafsir.id,
                "label": "New Version",
                "version_number": "7.0",
                "summary": "This is a new version",
                "file": file,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("7.0", body["name"])
        self.assertEqual("New Version", body["label"])
        self.assertEqual("This is a new version", body["summary"])
        self.assertIsNotNone(body["file_url"])

        # Verify DB
        version = AssetVersion.objects.get(id=body["id"])
        self.assertEqual(self.tafsir, version.asset)
        # The stored file is generated from the parsed entries (what gets reviewed).
        with version.file_url.open("rb") as handle:
            stored = handle.read().decode("utf-8")
        self.assertTrue(version.file_url.name.endswith(".csv"))
        self.assertIn("1,1,in the name", stored)
        self.assertEqual(len(stored.encode("utf-8")), version.size_bytes)
        self.assertEqual(version.size_bytes, body["size_bytes"])
        self.assertEqual(self.user, version.created_by)
        self.assertEqual("Test User", body["created_by"])

    def test_create_version_with_language_tags_the_version(self):
        # Arrange — register a French language on the tafsir
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.tafsir.get_or_create_source_language()
        AssetLanguage.objects.create(asset=self.tafsir, language="fr")
        file = SimpleUploadedFile("tafsir-fr.csv", b"surah,ayah,text\n1,1,au nom", content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={
                "asset_id": self.tafsir.id,
                "label": "French v1",
                "version_number": "7.0",
                "summary": "",
                "language": "fr",
                "file": file,
            },
        )

        # Assert — the version is tagged with the chosen language
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(id=response.json()["id"])
        self.assertEqual("fr", version.asset_language.language)

    def test_create_version_where_asset_id_mismatch_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={
                "asset_id": 99999,
                "label": "New Version",
                "version_number": "7.0",
                "file": SimpleUploadedFile("t.pdf", b"c"),
            },
        )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("asset_id_mismatch", response.json()["error_name"])

    def test_create_version_where_unauthenticated_should_return_401(self):
        response = self.client.post(f"/portal/tafsirs/{self.tafsir.slug}/versions/", data={})
        self.assertEqual(401, response.status_code)

    def test_create_version_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)
        file = SimpleUploadedFile("tafsir.pdf", b"content", content_type="application/pdf")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "V1", "version_number": "1.0", "file": file},
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_create_version_with_subscribers_should_not_send_email_before_publishing(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        baker.make(AssetVersion, asset=self.tafsir, name="1.0.0")
        subscriber = baker.make(User, email="tafsir-subscriber@example.com")
        access_request = baker.make(AssetAccessRequest, developer_user=subscriber, asset=self.tafsir, status="approved")
        baker.make(
            AssetAccess,
            asset_access_request=access_request,
            user=subscriber,
            asset=self.tafsir,
            effective_license="CC0",
        )
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/portal/tafsirs/{self.tafsir.slug}/versions/",
                data={
                    "asset_id": self.tafsir.id,
                    "label": "2.0.0",
                    "version_number": "1.0",
                    "summary": "New release",
                    "file": file,
                },
            )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        # Assert — an upload is not visible to consumers until it is published
        recipients = [email for m in mail.outbox for email in m.to]
        self.assertNotIn("tafsir-subscriber@example.com", recipients)

    def test_create_version_without_subscribers_should_not_send_email(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        baker.make(AssetVersion, asset=self.tafsir, name="1.0.0")  # prior version so this is an update
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "2.0.0", "version_number": "1.0", "file": file},
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_create_version_where_file_unparseable_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        file = SimpleUploadedFile("tafsir.pdf", b"content", content_type="application/pdf")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "v2", "version_number": "1.0", "file": file},
        )

        # Assert — content that cannot be split into units cannot be reviewed
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("content_file_unparseable", response.json()["error_name"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.tafsir, name="v2").exists())

    def test_create_version_where_rows_would_be_dropped_should_return_400_naming_them(self):
        # Arrange — row 3 repeats 1:1 with different text, row 4 names a missing ayah
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        content = b"surah,ayah,text\n1,1,in the name\n1,1,hidden text\n1,99,more hidden\n"
        file = SimpleUploadedFile("tafsir.csv", content, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "v2", "version_number": "1.0", "file": file},
        )

        # Assert — nothing whose text would be dropped (and so never reviewed) is accepted
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("content_file_invalid_rows", body["error_name"])
        self.assertEqual({"3": "duplicate", "4": "unknown_unit"}, body["extra"]["rows"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.tafsir, name="v2").exists())

    def test_create_version_where_extra_columns_should_store_only_the_reviewed_content(self):
        # Arrange — an extra column the parser ignores, so reviewers never see it
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        content = b"surah,ayah,text,notes\n1,1,in the name,secret note\n"
        file = SimpleUploadedFile("tafsir.csv", content, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "v2", "version_number": "1.0", "file": file},
        )

        # Assert — consumers download a file generated from the reviewed entries
        self.assertEqual(201, response.status_code, response.content)
        version = AssetVersion.objects.get(id=response.json()["id"])
        with version.file_url.open("rb") as handle:
            stored = handle.read().decode("utf-8")
        self.assertIn("in the name", stored)
        self.assertNotIn("secret note", stored)

    def test_create_version_where_content_differs_should_record_changes_for_review(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        previous = baker.make(AssetVersion, asset=self.tafsir, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="old text", order=1)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "v2", "version_number": "1.0", "file": file},
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        changes = list(AssetVersionChange.objects.filter(version_id=body["id"]))
        self.assertEqual(1, len(changes))
        self.assertEqual(
            ("modified", "old text", "in the name"), (changes[0].change_type, changes[0].old_text, changes[0].new_text)
        )
        self.assertFalse(body["is_approved"])
        self.assertEqual(1, body["pending_review_count"])

    def test_create_version_where_pre_approved_by_reviewer_should_approve_its_changes(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        self.give_permission(self.user, PermissionChoice.PORTAL_REVIEW_CONTENT)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "version_number": "1.0", "pre_approved": True, "file": file},
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        reviews = list(AssetVersionChangeReview.objects.filter(change__version_id=body["id"]))
        self.assertEqual(1, len(reviews))
        self.assertEqual((ReviewStateChoice.APPROVED, self.user), (reviews[0].state, reviews[0].reviewed_by))
        self.assertTrue(body["is_approved"])
        self.assertEqual(0, body["pending_review_count"])

    def test_create_version_where_pre_approved_without_review_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "version_number": "1.0", "pre_approved": True, "file": file},
        )

        # Assert — no version is created
        self.assertEqual(403, response.status_code, response.content)
        self.assertFalse(AssetVersion.objects.filter(asset=self.tafsir).exists())

    def test_create_version_where_identical_to_previous_should_record_no_changes(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        previous = baker.make(AssetVersion, asset=self.tafsir, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="in the name", order=1)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "label": "v2", "version_number": "1.0", "file": file},
        )

        # Assert — nothing new to review
        self.assertEqual(201, response.status_code, response.content)
        self.assertFalse(AssetVersionChange.objects.filter(version_id=response.json()["id"]).exists())
        self.assertTrue(response.json()["is_approved"])


class TafsirVersionUpdateTest(TafsirVersionBaseTest):
    def setUp(self):
        super().setUp()
        self.version = baker.make(AssetVersion, asset=self.tafsir, name="Old Name")

    def test_put_version_where_valid_data_should_return_200(self):
        from urllib.parse import urlencode

        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        payload = {
            "asset_id": self.tafsir.id,
            "label": "Updated Name",
            "summary": "Updated Summary",
        }

        # Act
        response = self.client.put(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/",
            data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )

        # Arrange
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Name", body["label"])
        self.assertEqual("Updated Summary", body["summary"])

        self.version.refresh_from_db()
        self.assertEqual("Updated Name", self.version.label)

    def test_patch_version_where_partial_data_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        from urllib.parse import urlencode

        payload = {
            "label": "Patched Name",
        }

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/",
            data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Patched Name", body["label"])
        self.assertEqual(self.version.summary, body["summary"])

    def test_patch_version_where_name_sent_should_keep_version_number(self):
        from urllib.parse import urlencode

        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/",
            data=urlencode({"name": "9.9", "label": "Renamed"}),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert — the label changes, the issued number does not
        self.assertEqual(200, response.status_code, response.content)
        self.version.refresh_from_db()
        self.assertEqual("Old Name", self.version.name)
        self.assertEqual("Renamed", self.version.label)

    def test_update_version_where_unauthenticated_should_return_401(self):
        response = self.client.patch(f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/", data={})
        self.assertEqual(401, response.status_code)

    def test_update_version_where_user_lacks_permission_should_return_403(self):
        from urllib.parse import urlencode

        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/",
            data=urlencode({"label": "X"}),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TafsirVersionDeleteTest(TafsirVersionBaseTest):
    def test_delete_version_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TAFSIR)
        version = baker.make(AssetVersion, asset=self.tafsir)

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(204, response.status_code)
        self.assertFalse(AssetVersion.objects.filter(id=version.id).exists())

    def test_delete_version_where_unauthenticated_should_return_401(self):
        version = baker.make(AssetVersion, asset=self.tafsir)
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/")
        self.assertEqual(401, response.status_code)

    def test_delete_version_where_user_lacks_permission_should_return_403(self):
        # Arrange
        version = baker.make(AssetVersion, asset=self.tafsir)
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_delete_version_where_published_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TAFSIR)
        version = baker.make(AssetVersion, asset=self.tafsir)
        AssetLanguage.objects.filter(asset=self.tafsir).update(published_version=version)

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])
        self.assertTrue(AssetVersion.objects.filter(id=version.id).exists())


class TafsirVersionFileReplaceTest(TafsirVersionBaseTest):
    def test_patch_version_where_file_replaced_on_published_version_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        version = baker.make(AssetVersion, asset=self.tafsir, name="v1")
        AssetLanguage.objects.filter(asset=self.tafsir).update(published_version=version)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/",
            data={"file": file},
        )

        # Assert — the published content cannot change underneath consumers
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])

    def test_patch_version_where_file_replaced_should_rerecord_changes_for_review(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        previous = baker.make(AssetVersion, asset=self.tafsir, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="old text", order=1)
        version = baker.make(AssetVersion, asset=self.tafsir, name="v2")
        baker.make(AssetVersionEntry, version=version, ayah=self.ayah, text="old text", order=1)
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/",
            data={"file": file},
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        change = AssetVersionChange.objects.get(version=version)
        self.assertEqual("in the name", change.new_text)


class TafsirVersionHistoryIsAppendOnlyTest(TafsirVersionBaseTest):
    """Later versions build on earlier ones, so only the newest may change."""

    def _two_versions(self) -> tuple[AssetVersion, AssetVersion]:
        older = baker.make(AssetVersion, asset=self.tafsir, name="v1")
        newer = baker.make(AssetVersion, asset=self.tafsir, name="v2")
        AssetVersion.objects.filter(pk=newer.pk).update(created_at=older.created_at + timezone.timedelta(hours=1))
        return older, newer

    def test_patch_version_where_file_replaced_on_older_version_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TAFSIR)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT)
        older, _newer = self._two_versions()
        file = SimpleUploadedFile("tafsir.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{older.id}/",
            data={"file": file},
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_latest", response.json()["error_name"])

    def test_delete_version_where_older_version_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TAFSIR)
        older, _newer = self._two_versions()

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{older.id}/")

        # Assert — kept: the newer version's changes are relative to it
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_not_latest", response.json()["error_name"])
        self.assertTrue(AssetVersion.objects.filter(id=older.id).exists())

    def test_delete_version_where_newest_version_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TAFSIR)
        _older, newer = self._two_versions()

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{newer.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(AssetVersion.objects.filter(id=newer.id).exists())
