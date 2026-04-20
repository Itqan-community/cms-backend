from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, Resource, ResourceVersion
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TranslationVersionBaseTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TRANSLATION,
            status=Resource.StatusChoice.READY,
        )
        self.translation = baker.make(
            Asset,
            category=Resource.CategoryChoice.TRANSLATION,
            resource=self.resource,
            name="Translation Al-Tabari",
            slug="translation-al-tabari",
        )
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)


class TranslationVersionListTest(TranslationVersionBaseTest):
    def test_list_versions_where_valid_slug_should_return_versions(self):
        # Arrange
        self.authenticate_user(self.user)
        rv1 = baker.make(ResourceVersion, resource=self.resource, semvar="1.0.0")
        rv2 = baker.make(ResourceVersion, resource=self.resource, semvar="2.0.0")
        baker.make(AssetVersion, asset=self.translation, resource_version=rv1, name="V1")
        baker.make(AssetVersion, asset=self.translation, resource_version=rv2, name="V2")

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

        # Act
        response = self.client.get("/portal/translations/non-existent/versions/")

        # Assert
        self.assertEqual(404, response.status_code)


class TranslationVersionCreateTest(TranslationVersionBaseTest):
    def test_create_version_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        file = SimpleUploadedFile("translation.pdf", b"content", content_type="application/pdf")

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
        self.assertEqual(len(b"content"), body["size_bytes"])

        # Verify DB
        version = AssetVersion.objects.get(id=body["id"])
        self.assertEqual(self.translation, version.asset)
        self.assertEqual("1.0.0", version.resource_version.semvar)
        self.assertEqual(len(b"content"), version.size_bytes)

    def test_create_version_where_asset_id_mismatch_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)

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


class TranslationVersionUpdateTest(TranslationVersionBaseTest):
    def setUp(self):
        super().setUp()
        rv = baker.make(ResourceVersion, resource=self.resource, semvar="1.0.0")
        # Ensure we have a valid file to avoid size calculation errors if needed
        self.version = baker.make(AssetVersion, asset=self.translation, resource_version=rv, name="Old Name")

    def test_put_version_where_valid_data_should_return_200(self):
        from urllib.parse import urlencode

        # Arrange
        self.authenticate_user(self.user)
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
        self.assertEqual("Updated Name", self.version.resource_version.name)

    def test_patch_version_where_partial_data_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
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


class TranslationVersionDeleteTest(TranslationVersionBaseTest):
    def test_delete_version_should_return_204(self):
        # Arrange
        self.authenticate_user(self.user)
        rv = baker.make(ResourceVersion, resource=self.resource)
        version = baker.make(AssetVersion, asset=self.translation, resource_version=rv)

        # Act
        response = self.client.delete(f"/portal/translations/{self.translation.slug}/versions/{version.id}/")

        # Assert
        self.assertEqual(204, response.status_code)
        self.assertFalse(AssetVersion.objects.filter(id=version.id).exists())
        self.assertFalse(ResourceVersion.objects.filter(id=rv.id).exists())
