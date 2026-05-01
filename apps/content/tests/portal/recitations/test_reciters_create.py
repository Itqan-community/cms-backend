from django.core.files.uploadedfile import SimpleUploadedFile

from apps.content.models import Reciter
from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.users.models import User


class ReciterCreateTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="testuser@example.com", name="Test User")

    def test_create_reciter_where_valid_data_should_return_201(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_RECITER)

        # Act
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name_ar": "مقرئ جديد",
                "name_en": "New Reciter",
                "bio_ar": "سيرة ذاتية",
                "bio_en": "Biography",
                "nationality": "EG",
                "date_of_death": "2020-01-01",
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()

        self.assertIsNotNone(body["id"])
        self.assertEqual("New Reciter", body["name"])
        self.assertEqual("EG", body["nationality"])
        self.assertEqual("مقرئ-جديد", body["slug"])

        reciter = Reciter.objects.get(id=body["id"])
        self.assertEqual("New Reciter", reciter.name)
        self.assertEqual("مقرئ-جديد", reciter.slug)
        self.assertEqual("EG", reciter.nationality.code)

    def test_create_reciter_where_duplicate_name_should_return_409(self):
        # Arrange
        Reciter.objects.create(name="Existing Reciter", slug="existing-reciter")
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_RECITER)

        # Act
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name_ar": "Existing Reciter",
                "name_en": "Existing Reciter",
            },
        )

        # Assert
        self.assertEqual(409, response.status_code)
        self.assertEqual("reciter_already_exists", response.json()["error_name"])

    def test_create_reciter_where_unauthenticated_should_return_401(self):
        # Arrange
        # No authentication setup

        # Act
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name_ar": "مقرئ جديد",
                "name_en": "New Reciter",
            },
        )

        # Assert
        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json().get("error_name"))

    def test_create_reciter_where_image_exists_should_return_201_and_upload_image(self):
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.CREATE_PORTAL_RECITER)
        image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")

        # Act
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name_ar": "مقرئ بصورة",
                "name_en": "Reciter With Image",
                "image": image,
            },
        )

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertIsNotNone(body["id"])

        reciter = Reciter.objects.get(id=body["id"])
        self.assertTrue(bool(reciter.image_url))
        self.assertTrue(reciter.image_url.name.startswith("uploads/reciters/"))
        self.assertTrue(reciter.image_url.name.endswith(".jpg"))

        # Clean up the file created during test
        reciter.image_url.delete()

    def test_create_reciter_where_user_lacks_permission_should_return_403(self):
        # Arrange
        user_without_permission = User.objects.create_user(email="noperm@example.com", name="No Permission User")
        self.authenticate_user(user_without_permission)

        # Act
        response = self.client.post(
            "/portal/reciters/",
            data={
                "name_ar": "مقرئ جديد",
                "name_en": "New Reciter",
            },
        )

        # Assert
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error_name"])
