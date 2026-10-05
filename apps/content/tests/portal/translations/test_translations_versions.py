from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetAccess,
    AssetAccessRequest,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.quran.models import Ayah, Sura
from apps.users.models import User

# A file that parses into entries: uploads must, so their content can be reviewed.
CSV = b"surah,ayah,text\n1,1,in the name"


class TranslationVersionBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.translation = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.AYAH,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Translation Al-Tabari",
            slug="translation-al-tabari",
        )
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)
        # These suites exercise editing, not language assignment: give the user the
        # assignment bypass so they behave like the existing editor groups that the
        # rollout migration grants it to. Assignment itself is covered by its own tests.
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES)
        sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=7)
        self.ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="a")


class TranslationVersionListTest(TranslationVersionBaseTest):
    def test_list_versions_where_valid_slug_should_return_versions(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
        baker.make(AssetVersion, asset=self.translation, name="V1")
        baker.make(AssetVersion, asset=self.translation, name="V2")

        # Act
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(2, len(body["results"]))
        self.assertEqual("V2", body["results"][0]["name"])  # Ordered by -created_at

    def test_list_versions_where_translation_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)

        # Act
        response = self.client.get("/portal/translations/non-existent/versions/")

        # Assert
        self.assertEqual(404, response.status_code)

    def test_list_versions_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/")
        self.assertEqual(401, response.status_code)

    def test_list_versions_where_user_lacks_permission_should_return_403(self):
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)
        response = self.client.get(f"/portal/translations/{self.translation.slug}/versions/")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TranslationVersionCreateTest(TranslationVersionBaseTest):
    def test_create_version_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": self.translation.id,
                "name": "New Version",
                "summary": "This is a new version",
                "file": file,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("New Version", body["name"])
        self.assertEqual("This is a new version", body["summary"])
        self.assertIsNotNone(body["file_url"])
        self.assertEqual(len(CSV), body["size_bytes"])

        # Verify DB
        version = AssetVersion.objects.get(id=body["id"])
        self.assertEqual(self.translation, version.asset)
        self.assertEqual(len(CSV), version.size_bytes)
        self.assertEqual(self.user, version.created_by)
        self.assertEqual("Test User", body["created_by"])

    def test_create_version_where_asset_id_mismatch_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": 99999,
                "name": "New Version",
                "file": SimpleUploadedFile("t.pdf", b"c"),
            },
        )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("asset_id_mismatch", response.json()["error_name"])

    def test_create_version_where_unauthenticated_should_return_401(self):
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": self.translation.id,
                "name": "New Version",
                "file": SimpleUploadedFile("t.pdf", b"c"),
            },
        )
        self.assertEqual(401, response.status_code)

    def test_create_version_where_user_lacks_permission_should_return_403(self):
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={
                "asset_id": self.translation.id,
                "name": "New Version",
                "file": SimpleUploadedFile("t.pdf", b"c"),
            },
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_create_version_with_subscribers_should_not_send_email_before_publishing(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        baker.make(AssetVersion, asset=self.translation, name="1.0.0")
        subscriber = baker.make(User, email="translation-subscriber@example.com")
        access_request = baker.make(
            AssetAccessRequest, developer_user=subscriber, asset=self.translation, status="approved"
        )
        baker.make(
            AssetAccess,
            asset_access_request=access_request,
            user=subscriber,
            asset=self.translation,
            effective_license="CC0",
        )
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/portal/translations/{self.translation.slug}/versions/",
                data={"asset_id": self.translation.id, "name": "2.0.0", "summary": "New release", "file": file},
            )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        # Assert — an upload is not visible to consumers until it is published
        recipients = [email for m in mail.outbox for email in m.to]
        self.assertNotIn("translation-subscriber@example.com", recipients)

    def test_create_version_without_subscribers_should_not_send_email(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        baker.make(AssetVersion, asset=self.translation, name="1.0.0")  # prior version so this is an update
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={"asset_id": self.translation.id, "name": "2.0.0", "file": file},
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_create_version_where_file_unparseable_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        file = SimpleUploadedFile("translation.pdf", b"content", content_type="application/pdf")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={"asset_id": self.translation.id, "name": "v2", "file": file},
        )

        # Assert — content that cannot be split into units cannot be reviewed
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("content_file_unparseable", response.json()["error_name"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.translation, name="v2").exists())

    def test_create_version_where_rows_would_be_dropped_should_return_400_naming_them(self):
        # Arrange — row 3 repeats 1:1 with different text, row 4 names a missing ayah
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        content = b"surah,ayah,text\n1,1,in the name\n1,1,hidden text\n1,99,more hidden\n"
        file = SimpleUploadedFile("translation.csv", content, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={"asset_id": self.translation.id, "name": "v2", "file": file},
        )

        # Assert — nothing whose text would be dropped (and so never reviewed) is accepted
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("content_file_invalid_rows", body["error_name"])
        self.assertEqual({"3": "duplicate", "4": "unknown_unit"}, body["extra"]["rows"])
        self.assertFalse(AssetVersion.objects.filter(asset=self.translation, name="v2").exists())

    def test_create_version_where_content_differs_should_record_changes_for_review(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        previous = baker.make(AssetVersion, asset=self.translation, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="old text", order=1)
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={"asset_id": self.translation.id, "name": "v2", "file": file},
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

    def test_create_version_where_identical_to_previous_should_record_no_changes(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        previous = baker.make(AssetVersion, asset=self.translation, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="in the name", order=1)
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.post(
            f"/portal/translations/{self.translation.slug}/versions/",
            data={"asset_id": self.translation.id, "name": "v2", "file": file},
        )

        # Assert — nothing new to review
        self.assertEqual(201, response.status_code, response.content)
        self.assertFalse(AssetVersionChange.objects.filter(version_id=response.json()["id"]).exists())
        self.assertTrue(response.json()["is_approved"])


class TranslationVersionUpdateTest(TranslationVersionBaseTest):
    def setUp(self):
        super().setUp()
        self.version = baker.make(AssetVersion, asset=self.translation, name="Old Name")

    def test_put_version_where_valid_data_should_return_200(self):
        from urllib.parse import urlencode

        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        payload = {
            "asset_id": self.translation.id,
            "name": "Updated Name",
            "summary": "Updated Summary",
        }

        # Act
        response = self.client.put(
            f"/portal/translations/{self.translation.slug}/versions/{self.version.id}/",
            data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )

        # Arrange
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Name", body["name"])
        self.assertEqual("Updated Summary", body["summary"])

        self.version.refresh_from_db()
        self.assertEqual("Updated Name", self.version.name)

    def test_patch_version_where_partial_data_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        from urllib.parse import urlencode

        payload = {
            "name": "Patched Name",
        }

        # Act
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/versions/{self.version.id}/",
            data=urlencode(payload),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Patched Name", body["name"])
        self.assertEqual(self.version.summary, body["summary"])

    def test_update_version_where_unauthenticated_should_return_401(self):
        from urllib.parse import urlencode

        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/versions/{self.version.id}/",
            data=urlencode({"name": "Updated"}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(401, response.status_code)

    def test_update_version_where_user_lacks_permission_should_return_403(self):
        from urllib.parse import urlencode

        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/versions/{self.version.id}/",
            data=urlencode({"name": "Updated"}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TranslationVersionDeleteTest(TranslationVersionBaseTest):
    def test_delete_version_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation)

        # Act
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(204, response.status_code)
        self.assertFalse(AssetVersion.objects.filter(id=version.id).exists())

    def test_delete_version_where_unauthenticated_should_return_401(self):
        version = baker.make(AssetVersion, asset=self.translation)
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{version.id}/")
        self.assertEqual(401, response.status_code)

    def test_delete_version_where_user_lacks_permission_should_return_403(self):
        version = baker.make(AssetVersion, asset=self.translation)
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{version.id}/")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_delete_version_where_published_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_TRANSLATION)
        version = baker.make(AssetVersion, asset=self.translation)
        AssetLanguage.objects.filter(asset=self.translation).update(published_version=version)

        # Act
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])
        self.assertTrue(AssetVersion.objects.filter(id=version.id).exists())


class TranslationVersionFileReplaceTest(TranslationVersionBaseTest):
    def test_patch_version_where_file_replaced_on_published_version_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        version = baker.make(AssetVersion, asset=self.translation, name="v1")
        AssetLanguage.objects.filter(asset=self.translation).update(published_version=version)
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/versions/{version.id}/",
            data={"file": file},
        )

        # Assert — the published content cannot change underneath consumers
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("version_is_published", response.json()["error_name"])

    def test_patch_version_where_file_replaced_should_rerecord_changes_for_review(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self.give_permission(self.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)
        previous = baker.make(AssetVersion, asset=self.translation, name="v1")
        baker.make(AssetVersionEntry, version=previous, ayah=self.ayah, text="old text", order=1)
        version = baker.make(AssetVersion, asset=self.translation, name="v2")
        baker.make(AssetVersionEntry, version=version, ayah=self.ayah, text="old text", order=1)
        file = SimpleUploadedFile("translation.csv", CSV, content_type="text/csv")

        # Act
        response = self.client.patch(
            f"/portal/translations/{self.translation.slug}/versions/{version.id}/",
            data={"file": file},
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        change = AssetVersionChange.objects.get(version=version)
        self.assertEqual("in the name", change.new_text)
