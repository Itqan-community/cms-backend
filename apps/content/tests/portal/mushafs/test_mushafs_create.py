from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class MushafCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher, name="Test Publisher")
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)

    def test_create_mushaf_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف المدينة",
                "name_en": "Mushaf Al-Madinah",
                "description_ar": "مصحف شامل",
                "description_en": "A comprehensive mushaf",
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
        self.assertEqual("مصحف المدينة", body["name_ar"])
        self.assertEqual("Mushaf Al-Madinah", body["name_en"])
        self.assertEqual("CC-BY", body["license"])
        self.assertEqual("ar", body["language"])
        self.assertEqual(self.publisher.id, body["publisher"]["id"])

        # Verify in database
        asset = Asset.objects.get(id=body["id"])
        self.assertEqual(CategoryChoice.MUSHAF, asset.category)
        self.assertEqual(StatusChoice.READY, asset.status)
        self.assertEqual("ar", asset.language)

    def test_create_mushaf_where_publisher_not_found_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف",
                "name_en": "Mushaf",
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

    def test_create_mushaf_where_name_missing_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
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
        self.assertEqual("mushaf_name_required", body["error_name"])

    def test_create_mushaf_where_unauthenticated_should_return_401(self):
        # Arrange

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف",
                "name_en": "Mushaf",
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

    def test_create_mushaf_where_only_english_name_should_create_successfully(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "",
                "name_en": "English Mushaf",
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
        self.assertEqual("English Mushaf", body["name_en"])

    def test_create_mushaf_where_thumbnail_provided_should_upload_and_return_url(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)
        image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف مصور",
                "name_en": "Visual Mushaf",
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

    def test_create_mushaf_where_is_external_true_and_url_present_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف خارجي",
                "name_en": "External Mushaf",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": True,
                "external_url": "https://example.com/mushaf",
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_external"])
        self.assertEqual("https://example.com/mushaf", body["external_url"])

    def test_create_mushaf_where_is_external_true_and_no_url_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف خارجي",
                "name_en": "External Mushaf",
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

    def test_create_mushaf_defaults_visibility_flags_to_false(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_en": "Default Visibility Mushaf",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["is_open_access"])
        self.assertFalse(body["restricted_for_tenant"])
        asset = Asset.objects.get(id=body["id"])
        self.assertFalse(asset.is_open_access)
        self.assertFalse(asset.restricted_for_tenant)

    def test_create_mushaf_sets_visibility_flags(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_en": "Open Tenant-only Mushaf",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
                "is_open_access": True,
                "restricted_for_tenant": True,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["is_open_access"])
        self.assertTrue(body["restricted_for_tenant"])
        asset = Asset.objects.get(id=body["id"])
        self.assertTrue(asset.is_open_access)
        self.assertTrue(asset.restricted_for_tenant)

    def test_create_mushaf_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.post(
            "/portal/mushafs/",
            data={
                "name_ar": "مصحف",
                "name_en": "Mushaf",
                "license": "CC-BY",
                "language": "ar",
                "publisher_id": self.publisher.id,
                "is_external": False,
            },
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
