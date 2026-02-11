from model_bakery import baker

from apps.content.models import Resource
from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class CategoryListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.domain = baker.make(Domain, publisher=self.publisher, domain="example.com")
        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")

    def test_list_categories_returns_all_choices(self):
        """Test that all resource category choices are returned"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Should be a list, not a paginated response
        self.assertIsInstance(body, list)

        # Should return all category choices
        expected_count = len(Resource.CategoryChoice.choices)
        self.assertEqual(expected_count, len(body))

    def test_list_categories_response_schema(self):
        """Test that response contains all required fields with correct structure"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()

        # Verify structure
        for item in items:
            self.assertIn("value", item)
            self.assertIn("label", item)
            self.assertIsInstance(item["value"], str)
            self.assertIsInstance(item["label"], str)

    def test_list_categories_contains_expected_values(self):
        """Test that response contains all expected category values"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        category_values = {item["value"] for item in items}

        # Check for all expected categories
        expected_categories = {
            Resource.CategoryChoice.RECITATION.value,
            Resource.CategoryChoice.MUSHAF.value,
            Resource.CategoryChoice.TAFSIR.value,
            Resource.CategoryChoice.PROGRAM.value,
            Resource.CategoryChoice.LINGUISTIC.value,
            Resource.CategoryChoice.TRANSLATION.value,
            Resource.CategoryChoice.FONT.value,
            Resource.CategoryChoice.SEARCH.value,
            Resource.CategoryChoice.TAJWEED.value,
        }

        self.assertEqual(expected_categories, category_values)

    def test_list_categories_contains_expected_labels(self):
        """Test that response contains all expected category labels"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        category_labels = {item["label"] for item in items}

        # Check for all expected labels
        expected_labels = {choice.label for choice in Resource.CategoryChoice}

        self.assertEqual(expected_labels, category_labels)

    def test_list_categories_exact_response(self):
        """Test the exact response format and content"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()

        # Build expected response
        expected_items = [{"value": choice.value, "label": choice.label} for choice in Resource.CategoryChoice]

        # Sort both for comparison (order shouldn't matter for this endpoint)
        items_sorted = sorted(items, key=lambda x: x["value"])
        expected_sorted = sorted(expected_items, key=lambda x: x["value"])

        self.assertEqual(expected_sorted, items_sorted)

    def test_list_categories_is_static(self):
        """Test that categories list is static and doesn't depend on database state"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act - Get categories before creating any resources
        response1 = self.client.get("/tenant/categories/")
        self.assertEqual(200, response1.status_code)
        categories1 = response1.json()

        # Create some resources
        baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.MUSHAF,
            status=Resource.StatusChoice.DRAFT,
        )

        # Act - Get categories after creating resources
        response2 = self.client.get("/tenant/categories/")
        self.assertEqual(200, response2.status_code)
        categories2 = response2.json()

        # Assert - Should be identical
        self.assertEqual(categories1, categories2)

    def test_list_categories_value_label_mapping(self):
        """Test that each category has the correct value-label mapping"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/categories/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()

        # Create a mapping for easier lookup
        value_to_label = {item["value"]: item["label"] for item in items}

        # Verify specific mappings
        for choice in Resource.CategoryChoice:
            self.assertIn(choice.value, value_to_label)
            self.assertEqual(choice.label, value_to_label[choice.value])
