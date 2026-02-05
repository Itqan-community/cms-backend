from model_bakery import baker
from oauth2_provider.models import Application

from apps.content.models import Asset, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class RiwayahsListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.reciter = baker.make("content.Reciter", name="Test Reciter")
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

        # Active riwayahs with ready recitations
        self.active_riwayah_hafs = baker.make(Riwayah, is_active=True, name="Hafs", slug="hafs")
        self.valid_asset_hafs = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah_hafs,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        self.active_riwayah_warsh = baker.make(Riwayah, is_active=True, name="Warsh", slug="warsh")
        self.valid_asset_warsh = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah_warsh,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        self.active_riwayah_qaloon = baker.make(Riwayah, is_active=True, name="Qaloon", slug="qaloon")
        self.valid_asset_qaloon = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah_qaloon,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Multiple assets for same riwayah
        self.valid_asset_hafs_2 = baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah_hafs,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Inactive riwayah – should not appear
        self.inactive_riwayah = baker.make(Riwayah, is_active=False, name="Inactive Riwayah", slug="inactive")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.inactive_riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Asset with non-RECITATION category – should not count
        baker.make(
            Asset,
            category=Asset.CategoryChoice.TAFSIR,
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
            riwayah=self.active_riwayah_hafs,
            resource=draft_resource,
            reciter=self.reciter,
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
            riwayah=self.active_riwayah_hafs,
            resource=tafsir_resource,
            reciter=self.reciter,
        )

        # Riwayah with no assets
        baker.make(Riwayah, is_active=True, name="No Assets Riwayah", slug="no-assets")

        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def test_list_riwayahs_should_return_only_active_with_ready_recitations(self):
        """Test that only active riwayahs with READY recitations are returned"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        riwayah_names = {item["name"] for item in items}

        # Should only contain active riwayahs with ready recitations
        self.assertIn("Hafs", riwayah_names)
        self.assertIn("Warsh", riwayah_names)
        self.assertIn("Qaloon", riwayah_names)
        self.assertNotIn("Inactive Riwayah", riwayah_names)
        self.assertNotIn("No Assets Riwayah", riwayah_names)

        self.assertEqual(3, len(items))

    def test_list_riwayahs_recitations_count_includes_multiple_assets(self):
        """Test that recitations_count includes all READY recitations for a riwayah"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Find Hafs riwayah which has 2 valid assets
        hafs_item = next(item for item in items if item["name"] == "Hafs")
        self.assertEqual(self.active_riwayah_hafs.id, hafs_item["id"])
        self.assertEqual(2, hafs_item["recitations_count"])

        # Warsh and Qaloon should have 1 recitation each
        warsh_item = next(item for item in items if item["name"] == "Warsh")
        self.assertEqual(1, warsh_item["recitations_count"])

        qaloon_item = next(item for item in items if item["name"] == "Qaloon")
        self.assertEqual(1, qaloon_item["recitations_count"])

    def test_list_riwayahs_ordering_by_name(self):
        """Test that riwayahs can be ordered by name"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_riwayahs_search_by_name(self):
        """Test searching riwayahs by name"""
        # Arrange
        self.authenticate_client(self.app)

        # Act - search for "hafs"
        response = self.client.get("/riwayahs/?search=Hafs")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        riwayah_names = {item["name"] for item in items}
        self.assertIn("Hafs", riwayah_names)

    def test_list_riwayahs_search_by_slug(self):
        """Test searching riwayahs by slug"""
        # Arrange
        self.authenticate_client(self.app)

        # Act - search for "qaloon"
        response = self.client.get("/riwayahs/?search=qaloon")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        riwayah_names = {item["name"] for item in items}
        self.assertIn("Qaloon", riwayah_names)

    def test_list_riwayahs_search_case_insensitive(self):
        """Test that search is case-insensitive"""
        # Arrange
        self.authenticate_client(self.app)

        # Act - search with uppercase
        response = self.client.get("/riwayahs/?search=WARSH")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        riwayah_names = {item["name"] for item in items}
        self.assertIn("Warsh", riwayah_names)

    def test_list_riwayahs_pagination_default_limit(self):
        """Test pagination with default limit"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertIn("count", body)
        self.assertIn("results", body)
        self.assertEqual(3, body["count"])  # Should have 3 active riwayahs with recitations

    def test_list_riwayahs_pagination_limit_parameter(self):
        """Test pagination with custom limit"""
        # Arrange
        self.authenticate_client(self.app)

        # Act - request with limit=2
        response = self.client.get("/riwayahs/?limit=2")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(3, body["count"])  # Total count should still be 3

    def test_list_riwayahs_response_schema(self):
        """Test that response contains all required fields"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertGreater(len(items), 0)

        item = items[0]
        self.assertIn("id", item)
        self.assertIn("name", item)
        self.assertIn("recitations_count", item)

        # Validate types
        self.assertIsInstance(item["id"], int)
        self.assertIsInstance(item["name"], str)
        self.assertIsInstance(item["recitations_count"], int)

    def test_list_riwayahs_no_inactive_riwayahs_returned(self):
        """Test that inactive riwayahs are never returned"""
        # Arrange
        self.authenticate_client(self.app)
        # Create an active riwayah and make it inactive
        riwayah = baker.make(Riwayah, is_active=False, name="Test Inactive")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        riwayah_names = {item["name"] for item in items}
        self.assertNotIn("Test Inactive", riwayah_names)

    def test_list_riwayahs_no_draft_resources_counted(self):
        """Test that riwayahs with only draft recitations are not returned"""
        # Arrange
        self.authenticate_client(self.app)
        riwayah = baker.make(Riwayah, is_active=True, name="Draft Only Riwayah")
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=riwayah,
            resource=draft_resource,
            reciter=self.reciter,
        )

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        riwayah_names = {item["name"] for item in items}
        self.assertNotIn("Draft Only Riwayah", riwayah_names)

    def test_list_riwayahs_recitations_count_excludes_draft(self):
        """Test that recitations_count doesn't include draft resources"""
        # Arrange
        self.authenticate_client(self.app)
        # Add a draft asset to Hafs
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=self.active_riwayah_hafs,
            resource=draft_resource,
            reciter=self.reciter,
        )

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        hafs_item = next(item for item in items if item["name"] == "Hafs")
        # Should still be 2 (draft not counted)
        self.assertEqual(2, hafs_item["recitations_count"])

    def test_list_riwayahs_ordering_desc(self):
        """Test reverse ordering by name"""
        # Arrange
        self.authenticate_client(self.app)

        # Act - reverse ordering
        response = self.client.get("/riwayahs/?ordering=-name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names, reverse=True), names)

    def test_list_riwayahs_filter_and_ordering_combined(self):
        """Test search and ordering together"""
        # Arrange
        self.authenticate_client(self.app)

        # Add another riwayah with similar name
        similar_riwayah = baker.make(Riwayah, is_active=True, name="Hafs Extended")
        baker.make(
            Asset,
            category=Asset.CategoryChoice.RECITATION,
            riwayah=similar_riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Act - search by name containing "Hafs" and order by name
        response = self.client.get("/riwayahs/?search=Hafs&ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertGreater(len(items), 0)
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_riwayahs_response_includes_all_fields(self):
        """Test that all fields are returned in response"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        items = body["results"]
        self.assertGreater(len(items), 0)

        # Check required fields
        for item in items:
            self.assertIsNotNone(item.get("id"))
            self.assertIsNotNone(item.get("name"))
            self.assertGreaterEqual(item.get("recitations_count", 0), 0)

    def test_list_riwayahs_recitations_count_accuracy(self):
        """Test that recitations_count is accurately calculated"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Verify counts
        counts = {item["name"]: item["recitations_count"] for item in items}
        self.assertEqual(counts["Hafs"], 2)
        self.assertEqual(counts["Warsh"], 1)
        self.assertEqual(counts["Qaloon"], 1)

    def test_list_riwayahs_returns_paginated_response(self):
        """Test that response includes pagination metadata"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        # Check pagination fields exist
        self.assertIn("count", body)
        self.assertIn("results", body)
        self.assertIsInstance(body["count"], int)
        self.assertIsInstance(body["results"], list)

    def test_list_riwayahs_with_empty_search(self):
        """Test that empty search returns all results"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/?search=")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        # Empty search should return all items
        self.assertEqual(3, body["count"])

    def test_list_riwayahs_response_is_json(self):
        """Test that response is valid JSON"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("application/json", response["Content-Type"])

        # Should not raise exception
        data = response.json()
        self.assertIsInstance(data, dict)

    def test_list_riwayahs_each_riwayah_has_unique_id(self):
        """Test that each riwayah in response has a unique ID"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        ids = [item["id"] for item in items]
        # All IDs should be unique
        self.assertEqual(len(ids), len(set(ids)))

    def test_list_riwayahs_name_and_id_match_model(self):
        """Test that returned names match the database"""
        # Arrange
        self.authenticate_client(self.app)

        # Act
        response = self.client.get("/riwayahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Find specific riwayahs and verify their details
        hafs_item = next(item for item in items if item["id"] == self.active_riwayah_hafs.id)
        self.assertEqual("Hafs", hafs_item["name"])

        warsh_item = next(item for item in items if item["id"] == self.active_riwayah_warsh.id)
        self.assertEqual("Warsh", warsh_item["name"])
