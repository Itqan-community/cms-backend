from model_bakery import baker

from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User


class CreateReciterTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/reciters/"

    def test_create_reciter_where_all_fields_provided_should_return_201(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "Mishary Rashid Alafasy",
            "name_ar": "مشاري راشد العفاسي",
            "name_en": "Mishary Rashid Alafasy",
            "bio": "A famous Quran reciter from Kuwait",
            "bio_ar": "قارئ قرآن شهير من الكويت",
            "bio_en": "A famous Quran reciter from Kuwait",
            "is_active": True,
        }

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Mishary Rashid Alafasy", body["name"])
        self.assertEqual("mishary-rashid-alafasy", body["slug"])
        self.assertEqual("مشاري راشد العفاسي", body["name_ar"])
        self.assertEqual("Mishary Rashid Alafasy", body["name_en"])
        self.assertEqual("A famous Quran reciter from Kuwait", body["bio"])
        self.assertEqual("قارئ قرآن شهير من الكويت", body["bio_ar"])
        self.assertTrue(body["is_active"])
        self.assertIn("id", body)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_create_reciter_where_only_name_provided_should_return_201_with_defaults(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "Minimal Reciter"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Minimal Reciter", body["name"])
        self.assertEqual("minimal-reciter", body["slug"])
        self.assertEqual("", body["bio"])
        self.assertTrue(body["is_active"])

    def test_create_reciter_where_name_empty_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": ""}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("reciter_name_required", body["error_name"])

    def test_create_reciter_where_duplicate_slug_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Reciter, name="Test Reciter", slug="test-reciter")
        data = {"name": "Test Reciter"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("reciter_already_exists", body["error_name"])

    def test_create_reciter_where_translated_fields_provided_should_store_correctly(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "Saad Al-Ghamdi",
            "name_ar": "سعد الغامدي",
            "bio_ar": "من أشهر قراء القرآن الكريم",
        }

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("سعد الغامدي", body["name_ar"])
        self.assertEqual("من أشهر قراء القرآن الكريم", body["bio_ar"])

        # Verify in database
        reciter = Reciter.objects.get(id=body["id"])
        self.assertEqual("سعد الغامدي", reciter.name_ar)
        self.assertEqual("من أشهر قراء القرآن الكريم", reciter.bio_ar)

    def test_create_reciter_where_inactive_should_store_correctly(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "Inactive Reciter", "is_active": False}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertFalse(body["is_active"])

    def test_create_reciter_where_unauthenticated_should_return_401(self) -> None:
        # Arrange
        data = {"name": "Test Reciter"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
