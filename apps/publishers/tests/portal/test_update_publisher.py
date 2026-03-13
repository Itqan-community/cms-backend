from model_bakery import baker

from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class UpdatePublisherTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.publisher = baker.make(
            Publisher,
            name="Original Publisher",
            slug="original-publisher",
            description="Original description",
            address="Original address",
            website="https://original.com",
            contact_email="original@test.com",
            is_verified=True,
            foundation_year=2000,
            country="Egypt",
        )
        self.url = f"/portal/publishers/{self.publisher.id}/"

    def test_put_publisher_where_valid_data_should_return_200(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "Updated Publisher",
            "description": "Updated description",
            "address": "Updated address",
            "website": "https://updated.com",
            "contact_email": "updated@test.com",
            "is_verified": False,
            "foundation_year": 2020,
            "country": "Saudi Arabia",
        }

        # Act
        response = self.client.put(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Publisher", body["name"])
        self.assertEqual("updated-publisher", body["slug"])
        self.assertEqual("Updated description", body["description"])
        self.assertFalse(body["is_verified"])
        self.assertEqual(2020, body["foundation_year"])
        self.assertEqual("Saudi Arabia", body["country"])

    def test_put_publisher_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "Updated"}

        # Act
        response = self.client.put(
            "/portal/publishers/99999/", data, content_type="application/json"
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_not_found", body["error_name"])

    def test_patch_publisher_where_partial_data_should_update_only_provided_fields(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"country": "Jordan"}

        # Act
        response = self.client.patch(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Jordan", body["country"])
        # Other fields unchanged
        self.assertEqual("Original Publisher", body["name"])
        self.assertEqual("original-publisher", body["slug"])
        self.assertEqual("Original description", body["description"])

    def test_patch_publisher_where_name_changed_should_regenerate_slug(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name": "New Name Publisher"}

        # Act
        response = self.client.patch(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("New Name Publisher", body["name"])
        self.assertEqual("new-name-publisher", body["slug"])

    def test_patch_publisher_where_translated_fields_updated_should_persist(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        data = {"name_ar": "الناشر المحدث", "description_ar": "وصف محدث"}

        # Act
        response = self.client.patch(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("الناشر المحدث", body["name_ar"])
        self.assertEqual("وصف محدث", body["description_ar"])

    def test_update_publisher_where_unauthenticated_should_return_401(self) -> None:
        # Arrange
        data = {"name": "Updated"}

        # Act
        response = self.client.patch(self.url, data, content_type="application/json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
