from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.users.models import User
from apps.content.models import Reciter


class ReciterCreateTest(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)

    def test_create_reciter_success(self):
        self.authenticate_user(self.user)

        image = SimpleUploadedFile(
            "pic.png",
            b"file_content",
            content_type="image/png"
        )

        payload = {
            "name": "Mishary Alafasy",
            "nationality": "Kuwaiti",
            "date_of_birth": "1976-09-05",
            "date_of_death": "1976-09-05",
            "slug": "mishary-alafasy",
            "is_active": "true",
            "bio": "Famous Quran reciter",
            "reciter_identifier": "mishary001",
        }

        response = self.client.post(
            "/cms-api/reciters/",
            data={**payload, "image_url": image},
            format="multipart"
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["name"], payload["name"])
        self.assertIn("id", data)

        self.assertTrue(
            Reciter.objects.filter(
                reciter_identifier="mishary001"
            ).exists()
        )
    
    def test_create_reciter_duplicate_identifier(self):
        """Test that creating a reciter with an existing reciter_identifier returns 400."""
        self.authenticate_user(self.user)

        baker.make(
            Reciter,
            name="Existing Reciter",
            reciter_identifier="mishary001",
            nationality="Kuwaiti",
            date_of_birth="1976-09-05",
            slug="existing-reciter",
        )

        image = SimpleUploadedFile(
            "pic.png",
            b"file_content",
            content_type="image/png"
        )

        payload = {
            "name": "Mishary Alafasy",
            "nationality": "Kuwaiti",
            "date_of_birth": "1976-09-05",
            "slug": "mishary-alafasy",
            "is_active": "true",
            "bio": "Famous Quran reciter",
            "reciter_identifier": "mishary001",
        }

        response = self.client.post(
            "/cms-api/reciters/",
            data={**payload, "image_url": image},
            format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Reciter with this identifier already exists", response.json()["message"])

    def test_create_reciter_duplicate_name(self):
        """Test that creating a reciter with an existing name returns 400."""
        self.authenticate_user(self.user)

        baker.make(
            Reciter,
            name="Mishary Alafasy",
            reciter_identifier="existing001",
            nationality="Kuwaiti",
            date_of_birth="1976-09-05",
            slug="existing-reciter",
        )

        image = SimpleUploadedFile(
            "pic.png",
            b"file_content",
            content_type="image/png"
        )

        payload = {
            "name": "Mishary Alafasy",  # duplicate name
            "nationality": "Kuwaiti",
            "date_of_birth": "1976-09-05",
            "slug": "mishary-alafasy-2",
            "is_active": "true",
            "bio": "Famous Quran reciter",
            "reciter_identifier": "mishary002",
        }

        response = self.client.post(
            "/cms-api/reciters/",
            data={**payload, "image_url": image},
            format="multipart"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Reciter with this name already exists", response.json()["message"])

