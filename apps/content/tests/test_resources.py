from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from apps.content.models import Asset, RecitationSurahTrack, Reciter, Resource, Riwayah, UsageEvent
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
        response = self.client.get("/cms-api/resources/")

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
        response = self.client.get("/cms-api/resources/?category=tafsir")

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
        response = self.client.get("/cms-api/resources/?status=ready")

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
        response = self.client.get(f"/cms-api/resources/?publisher_id={self.publisher1.id}")

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
        response = self.client.get("/cms-api/resources/?search=tafsir")

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
        response = self.client.get("/cms-api/resources/?ordering=name")

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
        response = self.client.get("/cms-api/resources/?ordering=-created_at")

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
            f"/cms-api/resources/?category=tafsir&status=ready&publisher_id={self.publisher1.id}"
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
        response = self.client.post("/cms-api/resources/", data=data, format="json")

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
        response = self.client.post("/cms-api/resources/", data=data, format="json")

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
        response = self.client.put(f"/cms-api/resources/{resource.id}/", data=data, format="json")

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
        response = self.client.patch(f"/cms-api/resources/{resource.id}/", data=data, format="json")

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
        response = self.client.put(f"/cms-api/resources/{resource.id}/", data=data, format="json")

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
        response = self.client.delete(f"/cms-api/resources/{resource.id}/")

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
        response = self.client.get(f"/cms-api/resources/{resource.id}/", format="json")

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
        response = self.client.get(f"/cms-api/resources/{resource.id}/", format="json")

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
            f"/cms-api/resources/{resource.id}/",
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


class ContentRecitersListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

        # Valid resource/asset that should be counted
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.active_reciter = baker.make(Reciter, is_active=True, name="Active Reciter")

        self.valid_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.recitation_resource,
        )

        # Inactive reciter should NOT appear
        self.inactive_reciter = baker.make(Reciter, is_active=False, name="Inactive Reciter")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.inactive_reciter,
            resource=self.recitation_resource,
        )

        # Asset with non-RECITATION category should NOT be counted
        self.other_category_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.BOOK,  # assuming another category exists
            reciter=self.active_reciter,
            resource=self.recitation_resource,
        )

        # Resource not READY should NOT be counted
        self.draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.draft_resource,
        )

        # Resource with non-RECITATION category should NOT be counted
        self.other_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=self.active_reciter,
            resource=self.other_resource,
        )

    def test_list_reciters_should_return_only_active_reciters_with_ready_recitations(self):
        # Act
        response = self.client.get("/reciters", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        reciter_names = {item["name"] for item in items}

        self.assertIn("Active Reciter", reciter_names)
        self.assertNotIn("Inactive Reciter", reciter_names)

        # There should be exactly one reciter (the active one with at least one valid asset)
        self.assertEqual(1, len(items))

        reciter_item = items[0]
        self.assertEqual(self.active_reciter.id, reciter_item["id"])
        # Only the valid RECITATION asset with READY + RECITATION resource should be counted
        self.assertEqual(1, reciter_item["recitations_count"])

    def test_list_reciters_ordering_by_name(self):
        # Arrange – another active reciter so we can test ordering
        other_reciter = baker.make(Reciter, is_active=True, name="A Reciter")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            reciter=other_reciter,
            resource=self.recitation_resource,
        )

        # Act
        response = self.client.get("/reciters?ordering=name", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)  # ascending by name


class ContentRiwayahsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

        self.active_riwayah = baker.make(Riwayah, is_active=True, name="Active Riwayah")
        self.valid_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=self.recitation_resource,
        )

        # Inactive riwayah – should not appear
        self.inactive_riwayah = baker.make(Riwayah, is_active=False, name="Inactive Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.inactive_riwayah,
            resource=self.recitation_resource,
        )

        # Asset with non-RECITATION category – should not count
        baker.make(
            Asset,
            category=Asset.CategoryChoice.BOOK,
            riwayah=self.active_riwayah,
            resource=self.recitation_resource,
        )

        # Resource not READY – should not count
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=draft_resource,
        )

        # Resource not RECITATION – should not count
        tafsir_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah,
            resource=tafsir_resource,
        )

    def test_list_riwayahs_should_return_only_active_with_ready_recitations(self):
        # Act
        response = self.client.get("/riwayahs", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        riwayah_names = {item["name"] for item in items}

        self.assertIn("Active Riwayah", riwayah_names)
        self.assertNotIn("Inactive Riwayah", riwayah_names)
        self.assertEqual(1, len(items))

        riwayah_item = items[0]
        self.assertEqual(self.active_riwayah.id, riwayah_item["id"])
        self.assertEqual(1, riwayah_item["recitations_count"])

    def test_list_riwayahs_ordering_by_name(self):
        other_riwayah = baker.make(Riwayah, is_active=True, name="A Riwayah")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=other_riwayah,
            resource=self.recitation_resource,
        )

        response = self.client.get("/riwayahs?ordering=name", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)


class ContentRecitationsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher1 = baker.make(Publisher, name="Publisher One")
        self.publisher2 = baker.make(Publisher, name="Publisher Two")
        self.reciter1 = baker.make(Reciter, name="Reciter One")
        self.reciter2 = baker.make(Reciter, name="Reciter Two")
        self.riwayah1 = baker.make(Riwayah)
        self.riwayah2 = baker.make(Riwayah)

        self.ready_recitation_resource_pub1 = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.ready_recitation_resource_pub2 = baker.make(
            Resource,
            publisher=self.publisher2,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.draft_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        self.other_category_resource = baker.make(
            Resource,
            publisher=self.publisher1,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )

        # Valid assets that should be returned
        self.asset1 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
            riwayah=self.riwayah1,
            name="First Recitation",
            description="Beautiful recitation",
        )
        self.asset2 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.ready_recitation_resource_pub2,
            reciter=self.reciter2,
            riwayah=self.riwayah2,
            name="Second Recitation",
            description="Calm recitation",
        )

        # Assets that should NOT be returned
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.draft_recitation_resource,
            reciter=self.reciter1,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.other_category_resource,
            reciter=self.reciter1,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.BOOK,
            resource=self.ready_recitation_resource_pub1,
            reciter=self.reciter1,
        )

    def test_list_recitations_should_return_only_ready_recitation_assets(self):
        response = self.client.get("/recitations", format="json")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]

        # Only two valid assets should be returned
        self.assertEqual(2, len(items))
        returned_ids = {item["id"] for item in items}
        self.assertIn(self.asset1.id, returned_ids)
        self.assertIn(self.asset2.id, returned_ids)

        # Check required fields
        for item in items:
            self.assertIn("id", item)
            self.assertIn("resource_id", item)
            self.assertIn("name", item)
            self.assertIn("slug", item)
            self.assertIn("description", item)
            self.assertIn("created_at", item)
            self.assertIn("updated_at", item)

    def test_list_recitations_filter_by_publisher(self):
        response = self.client.get(f"/recitations?publisher_id={self.publisher1.id}", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])
        self.assertEqual(self.ready_recitation_resource_pub1.id, items[0]["resource_id"])

    def test_list_recitations_filter_by_reciter(self):
        response = self.client.get(f"/recitations?reciter_id={self.reciter2.id}", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_filter_by_riwayah(self):
        response = self.client.get(f"/recitations?riwayah_id={self.riwayah1.id}", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

    def test_list_recitations_search_should_match_name_description_publisher_or_reciter(self):
        # Search by part of description
        response = self.client.get("/recitations?search=Beautiful", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset1.id, items[0]["id"])

        # Search by reciter name
        response = self.client.get("/recitations?search=Reciter Two", format="json")
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertEqual(self.asset2.id, items[0]["id"])

    def test_list_recitations_ordering_by_name(self):
        response = self.client.get("/recitations?ordering=name", format="json")

        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)


class ContentRecitationTracksTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        self.asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=self.recitation_resource,
        )

    def test_list_recitation_tracks_should_return_tracks_ordered_by_surah_number(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=2,
            surah_name="Al-Baqarah",
            surah_name_ar="البقرة",
            chapter_number=2,
            duration_ms=2000,
            size_bytes=1024,
        )
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
        )

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        self.assertEqual(2, len(items))

        # Ordered by surah_number ascending
        self.assertEqual(1, items[0]["surah_number"])
        self.assertEqual("Al-Fatihah", items[0]["surah_name"])
        self.assertEqual(2, items[1]["surah_number"])
        self.assertEqual("Al-Baqarah", items[1]["surah_name"])

    def test_list_recitation_tracks_should_include_audio_url_when_audio_file_exists(self):
        # Arrange
        audio_file = SimpleUploadedFile("test.mp3", b"dummy", content_type="audio/mpeg")
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=audio_file,
        )

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))

        item = items[0]
        self.assertIsNotNone(item["audio_url"])
        # In Django tests this should be built from http://testserver
        self.assertTrue(item["audio_url"].startswith("http://testserver/"))

    def test_list_recitation_tracks_should_set_audio_url_to_null_when_no_audio_file(self):
        # Arrange
        baker.make(
            RecitationSurahTrack,
            asset=self.asset,
            surah_number=1,
            surah_name="Al-Fatihah",
            surah_name_ar="الفاتحة",
            chapter_number=1,
            duration_ms=1000,
            size_bytes=512,
            audio_file=None,
        )

        # Act
        response = self.client.get(f"/recitations/{self.asset.id}", format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(1, len(items))
        self.assertIsNone(items[0]["audio_url"])

    def test_list_recitation_tracks_for_nonexistent_or_invalid_asset_should_return_404(self):
        # Non-existent asset
        response = self.client.get("/recitations/999999", format="json")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with wrong category should also 404 due to queryset filter
        non_recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        non_recitation_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.BOOK,
            resource=non_recitation_resource,
        )

        response = self.client.get(f"/recitations/{non_recitation_asset.id}", format="json")
        self.assertEqual(404, response.status_code, response.content)

        # Asset with RECITATION category but non-READY resource should 404
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        draft_asset = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            resource=draft_resource,
        )

        response = self.client.get(f"/recitations/{draft_asset.id}", format="json")
        self.assertEqual(404, response.status_code, response.content)
