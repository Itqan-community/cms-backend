from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirVersionBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.tafsir = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            publisher=self.publisher,
            status=StatusChoice.READY,
            name="Tafsir Al-Tabari",
            slug="tafsir-al-tabari",
        )
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)


class TafsirVersionListTest(TafsirVersionBaseTest):
    def test_list_versions_where_valid_slug_should_return_versions(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TAFSIR)
        baker.make(AssetVersion, asset=self.tafsir, name="V1")
        baker.make(AssetVersion, asset=self.tafsir, name="V2")

        # Act
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")

        # Assert
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(2, len(body["results"]))
        self.assertEqual("V2", body["results"][0]["name"])  # Ordered by -created_at

    def test_list_versions_where_tafsir_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.READ_PORTAL_TAFSIR)

        # Act
        response = self.client.get("/portal/tafsirs/non-existent/versions/")

        # Assert
        self.assertEqual(404, response.status_code)

    def test_list_versions_where_unauthenticated_should_return_401(self):
        response = self.client.get(f"/portal/tafsirs/{self.tafsir.slug}/versions/")
        self.assertEqual(401, response.status_code)

    def test_list_versions_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
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
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TAFSIR)
        file = SimpleUploadedFile("tafsir.pdf", b"content", content_type="application/pdf")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={
                "asset_id": self.tafsir.id,
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
        self.assertEqual(len(b"content"), body["size_bytes"])

        # Verify DB
        version = AssetVersion.objects.get(id=body["id"])
        self.assertEqual(self.tafsir, version.asset)
        self.assertEqual(len(b"content"), version.size_bytes)

    def test_create_version_where_asset_id_mismatch_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_TAFSIR)

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
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
        response = self.client.post(f"/portal/tafsirs/{self.tafsir.slug}/versions/", data={})
        self.assertEqual(401, response.status_code)

    def test_create_version_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)
        file = SimpleUploadedFile("tafsir.pdf", b"content", content_type="application/pdf")

        # Act
        response = self.client.post(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/",
            data={"asset_id": self.tafsir.id, "name": "V1", "file": file},
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TafsirVersionUpdateTest(TafsirVersionBaseTest):
    def setUp(self):
        super().setUp()
        self.version = baker.make(AssetVersion, asset=self.tafsir, name="Old Name")

    def test_put_version_where_valid_data_should_return_200(self):
        from urllib.parse import urlencode

        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.UPDATE_PORTAL_TAFSIR)
        payload = {
            "asset_id": self.tafsir.id,
            "name": "Updated Name",
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
        self.assertEqual("Updated Name", body["name"])
        self.assertEqual("Updated Summary", body["summary"])

        self.version.refresh_from_db()
        self.assertEqual("Updated Name", self.version.name)

    def test_patch_version_where_partial_data_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.UPDATE_PORTAL_TAFSIR)
        from urllib.parse import urlencode

        payload = {
            "name": "Patched Name",
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
        self.assertEqual("Patched Name", body["name"])
        self.assertEqual(self.version.summary, body["summary"])

    def test_update_version_where_unauthenticated_should_return_401(self):
        response = self.client.patch(f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/", data={})
        self.assertEqual(401, response.status_code)

    def test_update_version_where_user_lacks_permission_should_return_403(self):
        from urllib.parse import urlencode

        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.patch(
            f"/portal/tafsirs/{self.tafsir.slug}/versions/{self.version.id}/",
            data=urlencode({"name": "X"}),
            content_type="application/x-www-form-urlencoded",
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])


class TafsirVersionDeleteTest(TafsirVersionBaseTest):
    def test_delete_version_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.DELETE_PORTAL_TAFSIR)
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
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.delete(f"/portal/tafsirs/{self.tafsir.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
