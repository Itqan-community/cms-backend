from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RetrievePublisherTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def test_retrieve_publisher_where_exists_should_return_200_with_all_fields(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        publisher = baker.make(
            Publisher,
            name="Tafsir Center",
            slug="tafsir-center",
            name_ar="مركز التفسير",
            description="A leading publisher",
            address="Riyadh",
            website="https://tafsir.center",
            contact_email="info@tafsir.center",
            is_verified=True,
            foundation_year=2010,
            country="Saudi Arabia",
        )

        # Act
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(publisher.id, body["id"])
        self.assertEqual("Tafsir Center", body["name"])
        self.assertEqual("tafsir-center", body["slug"])
        self.assertEqual("A leading publisher", body["description"])
        self.assertEqual("Riyadh", body["address"])
        self.assertEqual("https://tafsir.center", body["website"])
        self.assertEqual("info@tafsir.center", body["contact_email"])
        self.assertTrue(body["is_verified"])
        self.assertEqual(2010, body["foundation_year"])
        self.assertEqual("Saudi Arabia", body["country"])
        self.assertIn("icon_url", body)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)

    def test_retrieve_publisher_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/publishers/99999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_retrieve_publisher_where_unauthenticated_should_return_401(self) -> None:
        # Arrange
        publisher = baker.make(Publisher, name="Test", slug="test")

        # Act
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_retrieve_publisher_where_has_translated_fields_should_include_them(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        publisher = baker.make(
            Publisher,
            name="International Publisher",
            slug="international-publisher",
            name_ar="الناشر الدولي",
            name_en="International Publisher EN",
            description_ar="وصف بالعربية",
            description_en="Description in English",
        )

        # Act
        response = self.client.get(f"/portal/publishers/{publisher.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("الناشر الدولي", body["name_ar"])
        self.assertEqual("International Publisher EN", body["name_en"])
        self.assertEqual("وصف بالعربية", body["description_ar"])
        self.assertEqual("Description in English", body["description_en"])
