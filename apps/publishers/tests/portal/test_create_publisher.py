from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class CreatePublisherTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/"

    def test_create_publisher_where_all_fields_provided_should_return_201(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "Tafsir Center",
            "name_ar": "مركز التفسير",
            "description": "A leading Tafsir publisher",
            "description_ar": "ناشر رائد في التفسير",
            "address": "Riyadh, KSA",
            "website": "https://tafsir.center",
            "contact_email": "info@tafsir.center",
            "is_verified": True,
            "foundation_year": 2010,
            "country": "Saudi Arabia",
        }

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("tafsir-center", body["slug"])
        self.assertEqual("مركز التفسير", body["name_ar"])
        self.assertEqual("A leading Tafsir publisher", body["description"])
        self.assertEqual("ناشر رائد في التفسير", body["description_ar"])
        self.assertEqual("Riyadh, KSA", body["address"])
        self.assertEqual("https://tafsir.center", body["website"])
        self.assertEqual("info@tafsir.center", body["contact_email"])
        self.assertTrue(body["is_verified"])
        self.assertEqual(2010, body["foundation_year"])
        self.assertEqual("Saudi Arabia", body["country"])
        self.assertIn("id", body)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_create_publisher_where_only_name_provided_should_return_201_with_defaults(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "Minimal Publisher"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Minimal Publisher", body["name"])
        self.assertEqual("minimal-publisher", body["slug"])
        self.assertEqual("", body["description"])
        self.assertEqual("", body["address"])
        self.assertTrue(body["is_verified"])
        self.assertIsNone(body["foundation_year"])

    def test_create_publisher_where_name_empty_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": ""}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_name_required", body["error_name"])

    def test_create_publisher_where_duplicate_slug_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Publisher, name="Test Publisher", slug="test-publisher")
        data = {"name": "Test Publisher"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_already_exists", body["error_name"])

    def test_create_publisher_where_translated_fields_provided_should_store_correctly(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "International Publisher",
            "name_ar": "الناشر الدولي",
            "name_en": "International Publisher EN",
            "description_ar": "وصف بالعربية",
        }

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("الناشر الدولي", body["name_ar"])
        self.assertEqual("International Publisher EN", body["name_en"])
        self.assertEqual("وصف بالعربية", body["description_ar"])

        # Verify in database
        publisher = Publisher.objects.get(id=body["id"])
        self.assertEqual("الناشر الدولي", publisher.name_ar)
        self.assertEqual("International Publisher EN", publisher.name_en)
        self.assertEqual("وصف بالعربية", publisher.description_ar)

    def test_create_publisher_where_unauthenticated_should_return_401(self) -> None:
        # Arrange
        data = {"name": "Test Publisher"}

        # Act
        response = self.client.post(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
