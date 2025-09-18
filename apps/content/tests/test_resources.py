from django.test import TestCase
from model_bakery import baker

from apps.content.models import Resource
from apps.publishers.models import Publisher
from apps.users.models import User
from apps.core.tests import BaseTestCase


class ResourceListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

    def test_list_resources_should_return_all_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        resource1 = baker.make(Resource, publisher=self.publisher1, name="Resource 1", category=Resource.CategoryChoice.TAFSIR)
        resource2 = baker.make(Resource, publisher=self.publisher2, name="Resource 2", category=Resource.CategoryChoice.MUSHAF)

        # Act
        response = self.client.get("/content/resources/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        
        # Check pagination structure
        self.assertIn("results", body)
        self.assertIn("count", body)
        
        items = body["results"]
        self.assertEqual(2, len(items))
        
        # Check resource structure
        resource_names = [item["name"] for item in items]
        self.assertIn("Resource 1", resource_names)
        self.assertIn("Resource 2", resource_names)
        
        # Check required fields are present
        for item in items:
            self.assertIn("id", item)
            self.assertIn("name", item)
            self.assertIn("description", item)
            self.assertIn("category", item)
            self.assertIn("status", item)
            self.assertIn("publisher", item)
            self.assertIn("created_at", item)
            self.assertIn("updated_at", item)
            
            # Check publisher structure
            self.assertIn("id", item["publisher"])
            self.assertIn("name", item["publisher"])
            
            # Check that datetime fields are serialized as strings
            self.assertIsInstance(item["created_at"], str)
            self.assertIsInstance(item["updated_at"], str)

    def test_list_resources_filter_by_category_should_return_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        tafsir_resource = baker.make(Resource, publisher=self.publisher1, category=Resource.CategoryChoice.TAFSIR)
        mushaf_resource = baker.make(Resource, publisher=self.publisher2, category=Resource.CategoryChoice.MUSHAF)

        # Act
        response = self.client.get("/content/resources/?category=tafsir")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(1, len(items))
        self.assertEqual("tafsir", items[0]["category"])

    def test_list_resources_filter_by_status_should_return_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        draft_resource = baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.DRAFT)
        ready_resource = baker.make(Resource, publisher=self.publisher2, status=Resource.StatusChoice.READY)

        # Act
        response = self.client.get("/content/resources/?status=ready")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(1, len(items))
        self.assertEqual("ready", items[0]["status"])

    def test_list_resources_filter_by_publisher_should_return_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        resource1 = baker.make(Resource, publisher=self.publisher1)
        resource2 = baker.make(Resource, publisher=self.publisher2)

        # Act
        response = self.client.get(f"/content/resources/?publisher_id={self.publisher1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(1, len(items))
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_resources_search_should_return_matching_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        resource1 = baker.make(Resource, publisher=self.publisher1, name="Tafsir Ibn Katheer", description="Classic tafsir")
        resource2 = baker.make(Resource, publisher=self.publisher2, name="Mushaf Uthmani", description="Uthmani script")

        # Act
        response = self.client.get("/content/resources/?search=tafsir")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(1, len(items))
        self.assertEqual("Tafsir Ibn Katheer", items[0]["name"])

    def test_list_resources_ordering_by_name_should_return_sorted_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Resource, publisher=self.publisher1, name="Zebra Resource")
        baker.make(Resource, publisher=self.publisher2, name="Alpha Resource")

        # Act
        response = self.client.get("/content/resources/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(2, len(items))
        self.assertEqual("Alpha Resource", items[0]["name"])
        self.assertEqual("Zebra Resource", items[1]["name"])

    def test_list_resources_ordering_by_created_at_descending_should_return_sorted_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        resource1 = baker.make(Resource, publisher=self.publisher1, name="First Resource")
        resource2 = baker.make(Resource, publisher=self.publisher2, name="Second Resource")

        # Act
        response = self.client.get("/content/resources/?ordering=-created_at")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(2, len(items))
        # Most recent first
        self.assertEqual("Second Resource", items[0]["name"])
        self.assertEqual("First Resource", items[1]["name"])

    def test_list_resources_with_multiple_filters_should_return_correctly_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Resource, publisher=self.publisher1, category=Resource.CategoryChoice.TAFSIR, status=Resource.StatusChoice.DRAFT)
        baker.make(Resource, publisher=self.publisher1, category=Resource.CategoryChoice.TAFSIR, status=Resource.StatusChoice.READY)
        baker.make(Resource, publisher=self.publisher2, category=Resource.CategoryChoice.MUSHAF, status=Resource.StatusChoice.READY)

        # Act
        response = self.client.get(f"/content/resources/?category=tafsir&status=ready&publisher_id={self.publisher1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        
        self.assertEqual(1, len(items))
        self.assertEqual("tafsir", items[0]["category"])
        self.assertEqual("ready", items[0]["status"])
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    # CRUD Tests
    def test_create_resource_should_return_200_with_resource_data(self):
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "Test Resource",
            "description": "A test resource description",
            "category": Resource.CategoryChoice.TAFSIR,
            "publisher_id": self.publisher1.id
        }

        # Act
        response = self.client.post("/content/resources/", data=data, format='json')

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Test Resource", body["name"])
        self.assertEqual("A test resource description", body["description"])
        self.assertEqual("tafsir", body["category"])
        self.assertEqual(self.publisher1.id, body["publisher_id"])
        self.assertEqual("draft", body["status"])  # Default status
        self.assertIn("id", body)
        self.assertIn("slug", body)
        self.assertIn("created_at", body)
        self.assertIn("updated_at", body)
        
        # Check that datetime fields are serialized as strings
        self.assertIsInstance(body["created_at"], str)
        self.assertIsInstance(body["updated_at"], str)

    def test_create_resource_with_invalid_data_should_return_422(self):
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "",  # Invalid: empty name
            "description": "A test resource description",
            "category": Resource.CategoryChoice.TAFSIR,
            "publisher_id": self.publisher1.id
        }

        # Act
        response = self.client.post("/content/resources/", data=data, format='json')

        # Assert
        self.assertEqual(422, response.status_code, response.content)

    def test_update_resource_should_return_200_with_updated_data(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, name="Original Name")
        data = {
            "name": "Updated Name",
            "description": "Updated description"
        }

        # Act
        response = self.client.put(f"/content/resources/{resource.id}/", data=data, format='json')

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Name", body["name"])
        self.assertEqual("Updated description", body["description"])

    def test_partial_update_resource_should_return_200_with_updated_data(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, name="Original Name", description="Original description")
        data = {
            "name": "Partially Updated Name"
        }

        # Act
        response = self.client.patch(f"/content/resources/{resource.id}/", data=data, format='json')

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Partially Updated Name", body["name"])
        self.assertEqual("Original description", body["description"])  # Should remain unchanged

    def test_delete_resource_should_return_200_and_remove_resource(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1)

        # Act
        response = self.client.delete(f"/content/resources/{resource.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertTrue(body["success"])

        # Verify resource is deleted
        self.assertFalse(Resource.objects.filter(id=resource.id).exists())

    def test_publish_resource_should_change_status_to_ready(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.DRAFT)

        # Act
        response = self.client.post(f"/content/resources/{resource.id}/publish/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("ready", body["status"])

        # Verify in database
        resource.refresh_from_db()
        self.assertEqual(Resource.StatusChoice.READY, resource.status)

    def test_unpublish_resource_should_change_status_to_draft(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.READY)

        # Act
        response = self.client.post(f"/content/resources/{resource.id}/unpublish/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("draft", body["status"])

        # Verify in database
        resource.refresh_from_db()
        self.assertEqual(Resource.StatusChoice.DRAFT, resource.status)

    def test_publish_already_published_resource_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.READY)

        # Act
        response = self.client.post(f"/content/resources/{resource.id}/publish/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)

    def test_unpublish_already_unpublished_resource_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.DRAFT)

        # Act
        response = self.client.post(f"/content/resources/{resource.id}/unpublish/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)

    def test_resource_operations_with_non_existent_id_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        non_existent_id = 99999

        # Test different operations
        operations = [
            ("PUT", f"/content/resources/{non_existent_id}/", {"name": "Test"}),
            ("PATCH", f"/content/resources/{non_existent_id}/", {"name": "Test"}),
            ("DELETE", f"/content/resources/{non_existent_id}/", None),
            ("POST", f"/content/resources/{non_existent_id}/publish/", None),
            ("POST", f"/content/resources/{non_existent_id}/unpublish/", None),
        ]

        for method, url, data in operations:
            with self.subTest(method=method, url=url):
                # Act
                if method == "PUT":
                    response = self.client.put(url, data=data, format='json')
                elif method == "PATCH":
                    response = self.client.patch(url, data=data, format='json')
                elif method == "DELETE":
                    response = self.client.delete(url)
                elif method == "POST":
                    response = self.client.post(url)

                # Assert
                self.assertEqual(404, response.status_code, f"Failed for {method} {url}: {response.content}")
