from model_bakery import baker

from apps.content.models import Resource, UsageEvent
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class ResourceListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = baker.make(User, email="test@example.com", is_active=True)
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")

    def test_list_resources_should_return_all_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(
            Resource,
            publisher=self.publisher1,
            name="Resource 1",
            category=Resource.CategoryChoice.TAFSIR,
        )
        baker.make(
            Resource,
            publisher=self.publisher2,
            name="Resource 2",
            category=Resource.CategoryChoice.MUSHAF,
        )

        # Act
        response = self.client.get("/resources/")

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
        baker.make(Resource, publisher=self.publisher1, category=Resource.CategoryChoice.TAFSIR)
        baker.make(Resource, publisher=self.publisher2, category=Resource.CategoryChoice.MUSHAF)

        # Act
        response = self.client.get("/resources/?category=tafsir")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(1, len(items))
        self.assertEqual("tafsir", items[0]["category"])

    def test_list_resources_filter_by_status_should_return_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Resource, publisher=self.publisher1, status=Resource.StatusChoice.DRAFT)
        baker.make(Resource, publisher=self.publisher2, status=Resource.StatusChoice.READY)

        # Act
        response = self.client.get("/resources/?status=ready")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(1, len(items))
        self.assertEqual("ready", items[0]["status"])

    def test_list_resources_filter_by_publisher_should_return_filtered_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Resource, publisher=self.publisher1)
        baker.make(Resource, publisher=self.publisher2)

        # Act
        response = self.client.get(f"/resources/?publisher_id={self.publisher1.id}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.publisher1.id, items[0]["publisher"]["id"])

    def test_list_resources_search_should_return_matching_resources(self):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(
            Resource,
            publisher=self.publisher1,
            name="Tafsir Ibn Katheer",
            description="Classic tafsir",
        )
        baker.make(
            Resource, publisher=self.publisher2, name="Mushaf Uthmani", description="Uthmani script"
        )

        # Act
        response = self.client.get("/resources/?search=tafsir")

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
        response = self.client.get("/resources/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(2, len(items))
        self.assertEqual("Alpha Resource", items[0]["name"])
        self.assertEqual("Zebra Resource", items[1]["name"])

    def test_list_resources_ordering_by_created_at_descending_should_return_sorted_resources(
        self,
    ):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(Resource, publisher=self.publisher1, name="First Resource")
        baker.make(Resource, publisher=self.publisher2, name="Second Resource")

        # Act
        response = self.client.get("/resources/?ordering=-created_at")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        self.assertEqual(2, len(items))
        # Most recent first
        self.assertEqual("Second Resource", items[0]["name"])
        self.assertEqual("First Resource", items[1]["name"])

    def test_list_resources_with_multiple_filters_should_return_correctly_filtered_resources(
        self,
    ):
        # Arrange
        self.authenticate_user(self.user)
        baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.MUSHAF,
            status=Resource.StatusChoice.READY,
        )

        # Act
        response = self.client.get(
            f"/resources/?category=tafsir&status=ready&publisher_id={self.publisher1.id}"
        )

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
            "publisher_id": self.publisher1.id,
        }

        # Act
        response = self.client.post("/resources/", data=data, format="json")

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

    def test_create_resource_with_invalid_data_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        data = {
            "name": "",  # Invalid: empty name
            "description": "A test resource description",
            "category": Resource.CategoryChoice.TAFSIR,
            "publisher_id": self.publisher1.id,
        }

        # Act
        response = self.client.post("/resources/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)

        # Verify the error message includes validation details
        body = response.json()
        self.assertEqual("validation_error", body["error_name"])
        self.assertIn("name", str(body["extra"]))  # Should mention the name field
        self.assertIn("at least 1 character", str(body["extra"]))  # Should mention minimum length

    def test_update_resource_should_return_200_with_updated_data(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, name="Original Name")
        data = {"name": "Updated Name", "description": "Updated description"}

        # Act
        response = self.client.put(f"/resources/{resource.id}/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Updated Name", body["name"])
        self.assertEqual("Updated description", body["description"])

    def test_partial_update_resource_should_return_200_with_updated_data(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(
            Resource,
            publisher=self.publisher1,
            name="Original Name",
            description="Original description",
        )
        data = {"name": "Partially Updated Name"}

        # Act
        response = self.client.patch(f"/resources/{resource.id}/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Partially Updated Name", body["name"])
        self.assertEqual("Original description", body["description"])  # Should remain unchanged

    def test_update_resource_with_empty_name_should_return_400(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1, name="Original Name")
        data = {"name": "", "description": "Updated description"}  # Invalid: empty name

        # Act
        response = self.client.put(f"/resources/{resource.id}/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)

        # Verify the error message includes validation details
        body = response.json()
        self.assertEqual("validation_error", body["error_name"])
        self.assertIn("name", str(body["extra"]))  # Should mention the name field
        self.assertIn("at least 1 character", str(body["extra"]))  # Should mention minimum length

    def test_delete_resource_should_return_200_and_remove_resource(self):
        # Arrange
        self.authenticate_user(self.user)
        resource = baker.make(Resource, publisher=self.publisher1)

        # Act
        response = self.client.delete(f"/resources/{resource.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify resource is deleted
        self.assertFalse(Resource.objects.filter(id=resource.id).exists())

    def test_resource_operations_with_non_existent_id_should_return_404(self):
        # Arrange
        self.authenticate_user(self.user)
        non_existent_id = 99999

        # Test different operations
        operations = [
            ("PUT", f"/resources/{non_existent_id}/", {"name": "Test"}),
            ("PATCH", f"/resources/{non_existent_id}/", {"name": "Test"}),
            ("DELETE", f"/resources/{non_existent_id}/", None),
            ("POST", f"/resources/{non_existent_id}/publish/", None),
            ("POST", f"/resources/{non_existent_id}/unpublish/", None),
        ]

        for method, url, data in operations:
            with self.subTest(method=method, url=url):
                # Act
                if method == "PUT":
                    response = self.client.put(url, data=data, format="json")
                elif method == "PATCH":
                    response = self.client.patch(url, data=data, format="json")
                elif method == "DELETE":
                    response = self.client.delete(url)
                elif method == "POST":
                    response = self.client.post(url)

                # Assert
                self.assertEqual(
                    404,
                    response.status_code,
                    f"Failed for {method} {url}: {response.content}",
                )

    def test_detail_resource_where_authenticated_user_should_create_usage_event(self):
        # Arrange
        user = baker.make(User, email="usage-event-test@example.com", is_active=True)
        self.authenticate_user(user)
        resource = baker.make(
            Resource,
            publisher=self.publisher1,
            name="Usage Event Test Resource",
            description="Test resource for usage event tracking",
        )

        # Act
        response = self.client.get(f"/resources/{resource.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify usage event was created in database
        usage_events = UsageEvent.objects.filter(
            developer_user=user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.RESOURCE,
            resource_id=resource.id,
        )
        self.assertEqual(1, usage_events.count())

        usage_event = usage_events.first()
        self.assertEqual(usage_event.developer_user, user)
        self.assertEqual(usage_event.usage_kind, UsageEvent.UsageKindChoice.VIEW)
        self.assertEqual(usage_event.subject_kind, UsageEvent.SubjectKindChoice.RESOURCE)
        self.assertEqual(usage_event.resource_id, resource.id)
        self.assertIsNone(usage_event.asset_id)
        self.assertEqual(usage_event.effective_license, "")
        self.assertIsInstance(usage_event.metadata, dict)

    def test_detail_resource_where_anonymous_user_should_not_create_usage_event(self):
        # Arrange - Clear authentication for anonymous user
        self.authenticate_user(None)
        resource = baker.make(
            Resource,
            publisher=self.publisher1,
            name="Anonymous Test Resource",
            description="Test resource for anonymous access",
        )

        # Act
        response = self.client.get(f"/resources/{resource.id}/", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify no usage event was created for anonymous user
        usage_events = UsageEvent.objects.filter(
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.RESOURCE,
            resource_id=resource.id,
        )
        self.assertEqual(0, usage_events.count())

    def test_detail_resource_where_authenticated_user_should_include_request_metadata(
        self,
    ):
        # Arrange
        user = baker.make(User, email="metadata@example.com", is_active=True)
        self.authenticate_user(user)
        resource = baker.make(
            Resource,
            publisher=self.publisher1,
            name="Metadata Test Resource",
            description="Test resource for request metadata",
        )

        # Act - Include custom headers
        response = self.client.get(
            f"/resources/{resource.id}/",
            format="json",
            headers={
                "user-agent": "Test Agent/1.0",
                "x-forwarded-for": "192.168.1.100",
            },
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)

        # Verify usage event was created with correct metadata
        usage_events = UsageEvent.objects.filter(
            developer_user=user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            subject_kind=UsageEvent.SubjectKindChoice.RESOURCE,
            resource_id=resource.id,
        )
        self.assertEqual(1, usage_events.count())

        usage_event = usage_events.first()
        self.assertEqual(usage_event.user_agent, "Test Agent/1.0")
        # Note: IP address capture depends on Django test client configuration
        # In real requests, this would capture the client IP
