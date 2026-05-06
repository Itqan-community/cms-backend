from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class TafsirCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_create_tafsir_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير الطبري",
                "name_en": "Tafsir Al-Tabari",
                "description_ar": "تفسير شامل",
                "description_en": "A comprehensive tafsir",
                "long_description_ar": "شرح تفصيلي",
                "long_description_en": "Detailed explanation",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()

        self.assertIsNotNone(body["id"])
        self.assertEqual("تفسير الطبري", body["name_ar"])
        self.assertEqual("Tafsir Al-Tabari", body["name_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual("ar", body["language"])
        self.assertEqual(self.publisher.id, body["publisher"]["id"])

        # Verify in database
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(CategoryChoice.TAFSIR, asset.category)
        self.assertEqual(StatusChoice.READY, asset.status)
        self.assertEqual("ar", asset.language)

    def test_create_tafsir_where_publisher_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": 99999,  # Non-existent publisher
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_create_tafsir_where_name_missing_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "",  # Empty name
                "name_en": "",  # Empty name
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("tafsir_name_required", body["error_name"])

    def test_create_tafsir_where_unauthenticated_should_return_401(self):
        # Arrange

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                "description_ar": "وصف",
                "description_en": "Description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        body = response.json()
        self.assertEqual("authentication_error", body["error_name"])

    def test_create_tafsir_where_only_english_name_should_create_successfully(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "",
                "name_en": "English Tafsir",
                "description_ar": "",
                "description_en": "English description",
                "long_description_ar": "",
                "long_description_en": "",
                "license": "CC-BY-SA",
                "language": "en",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("English Tafsir", body["name_en"])

    def test_create_tafsir_where_thumbnail_provided_should_upload_and_return_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)
        image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير مصور",
                "name_en": "Visual Tafsir",
                "description_ar": "وصف",
                "description_en": "Description",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "thumbnail": image,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()

        self.assertIsNotNone(body["thumbnail_url"])
        self.assertTrue(body["thumbnail_url"].endswith(".jpg"))

        asset = Asset.objects.get(id=body["id"])
        self.assertTrue(bool(asset.thumbnail_url))
        self.assertTrue(asset.thumbnail_url.name.endswith(".jpg"))

    def test_create_tafsir_where_is_external_true_and_url_present_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير خارجي",
                "name_en": "External Tafsir",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": True,
                "external_url": "https://example.com/tafsir",
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_external"])
        self.assertEqual("https://example.com/tafsir", body["external_url"])

    def test_create_tafsir_where_is_external_true_and_no_url_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير خارجي",
                "name_en": "External Tafsir",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": True,
                "external_url": "",  # Or absent
            },
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("external_url_required", body["error_name"])

    def test_create_tafsir_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.post(
            "/portal/tafsirs/",
            data={
                "name_ar": "تفسير",
                "name_en": "Tafsir",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
