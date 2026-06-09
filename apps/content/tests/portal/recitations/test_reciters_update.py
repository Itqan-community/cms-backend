from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import Reciter
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class ReciterUpdateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User", is_staff=True)
        self.reciter = Reciter.objects.create(
            name="Test Reciter",
            name_en="Test Reciter",
            name_ar="مقرئ تجريبي",
            slug="test-reciter",
            nationality="EG",
        )

    def test_update_reciter_where_valid_partial_data_should_return_200(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_RECITER)

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_en": "Updated Reciter", "nationality": "SA"},
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertEqual("Updated Reciter", body["name_en"])
        self.assertEqual("SA", body["nationality"])

        self.reciter.refresh_from_db()
        self.assertEqual("Updated Reciter", self.reciter.name_en)
        self.assertEqual("Updated Reciter", self.reciter.name)
        self.assertEqual("SA", self.reciter.nationality.code)

    def test_update_reciter_where_image_provided_should_update_image(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_RECITER)
        image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_en": "Updated Reciter", "image": image},
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.reciter.refresh_from_db()
        self.assertEqual("Updated Reciter", self.reciter.name_en)
        self.assertTrue(bool(self.reciter.image_url))
        self.assertTrue(self.reciter.image_url.name.startswith("uploads/reciters/"))

    def test_update_reciter_where_image_part_is_empty_should_return_200_and_keep_name(self):
        # Reproduces the multipart PATCH the CMS frontend sends with an empty image part,
        # which previously raised RawPostDataException because the JSON-body endpoint tried
        # to read request.body after the multipart stream had already been consumed.
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_RECITER)
        empty_image = SimpleUploadedFile("empty.png", b"", content_type="image/png")

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_en": "Updated Reciter", "image": empty_image},
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Updated Reciter", response.json()["name_en"])
        self.reciter.refresh_from_db()
        self.assertEqual("Updated Reciter", self.reciter.name_en)
        # Empty upload must not set an image
        self.assertFalse(bool(self.reciter.image_url))

    def test_update_reciter_where_empty_name_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_RECITER)

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_ar": "   ", "name_en": "   "},
        )

        # Assert
        self.assertEqual(400, response.status_code)
        self.assertEqual("reciter_name_required", response.json()["error_name"])

    def test_update_reciter_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_en": "Updated Reciter"},
        )

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json().get("error_name"))

    def test_update_reciter_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(
            email="noperm@example.com", name="No Permission User", is_staff=True
        )
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.patch(
            f"/portal/reciters/{self.reciter.slug}/",
            data={"name_en": "Updated Reciter"},
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
