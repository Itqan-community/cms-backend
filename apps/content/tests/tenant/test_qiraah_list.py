from model_bakery import baker

from apps.content.models import Asset, Qiraah, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class QiraahListTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.domain = baker.make(Domain, publisher=self.publisher, domain="example.com")
        self.reciter = baker.make("content.Reciter", name="Test Reciter")
        self.recitation_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

        # Create Qiraahs with multiple Riwayahs - use unique names to avoid constraint violations
        self.qiraah_asim = baker.make(Qiraah, is_active=True, name="Test Asim", slug="test-asim")
        self.riwayah_hafs = baker.make(
            Riwayah, is_active=True, name="Test Hafs", slug="test-hafs", qiraah=self.qiraah_asim
        )
        self.riwayah_qaloon = baker.make(
            Riwayah, is_active=True, name="Test Qaloon", slug="test-qaloon", qiraah=self.qiraah_asim
        )

        # Add recitations for Asim Qiraah
        self.asset_hafs = baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=self.riwayah_hafs,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )
        self.asset_qaloon = baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=self.riwayah_qaloon,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Create another Qiraah with one Riwayah
        self.qiraah_nafi = baker.make(Qiraah, is_active=True, name="Test Nafi", slug="test-nafi")
        self.riwayah_warsh = baker.make(
            Riwayah, is_active=True, name="Test Warsh", slug="test-warsh", qiraah=self.qiraah_nafi
        )
        self.asset_warsh = baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=self.riwayah_warsh,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Inactive Qiraah - should not appear
        self.inactive_qiraah = baker.make(Qiraah, is_active=False, name="Test Inactive Qiraah", slug="test-inactive")
        inactive_riwayah = baker.make(
            Riwayah,
            is_active=True,
            name="Test Inactive Riwayah",
            slug="test-inactive-riwayah",
            qiraah=self.inactive_qiraah,
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=inactive_riwayah,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Qiraah with inactive Riwayah - should not appear
        self.qiraah_hamza = baker.make(Qiraah, is_active=True, name="Test Hamza", slug="test-hamza")
        inactive_riwayah_hamza = baker.make(
            Riwayah, is_active=False, name="Test Inactive Hamza", slug="test-inactive-hamza", qiraah=self.qiraah_hamza
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=inactive_riwayah_hamza,
            resource=self.recitation_resource,
            reciter=self.reciter,
        )

        # Qiraah with draft resources - should not appear
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        qiraah_draft = baker.make(Qiraah, is_active=True, name="Test Draft Qiraah", slug="test-draft")
        riwayah_draft = baker.make(
            Riwayah, is_active=True, name="Test Draft Riwayah", slug="test-draft-riwayah", qiraah=qiraah_draft
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=riwayah_draft,
            resource=draft_resource,
            reciter=self.reciter,
        )

        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")

    def test_list_qiraahs_returns_only_active_with_ready_recitations(self):
        """Test that only active qiraahs with READY recitations are returned"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()

        self.assertIn("results", body)
        self.assertIn("count", body)

        items = body["results"]
        qiraah_names = {item["name"] for item in items}

        # Should only contain active qiraahs with ready recitations
        self.assertIn("Test Asim", qiraah_names)
        self.assertIn("Test Nafi", qiraah_names)
        self.assertNotIn("Test Inactive Qiraah", qiraah_names)
        self.assertNotIn("Test Hamza", qiraah_names)  # All riwayahs are inactive
        self.assertNotIn("Test Draft Qiraah", qiraah_names)  # Only draft resources

        self.assertEqual(2, len(items))

    def test_list_qiraahs_counts_active_riwayahs_correctly(self):
        """Test that riwayahs_count includes only active riwayahs"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Asim should have 2 active riwayahs
        asim_item = next(item for item in items if item["name"] == "Test Asim")
        self.assertEqual(2, asim_item["riwayahs_count"])

        # Nafi should have 1 active riwayah
        nafi_item = next(item for item in items if item["name"] == "Test Nafi")
        self.assertEqual(1, nafi_item["riwayahs_count"])

    def test_list_qiraahs_counts_recitations_correctly(self):
        """Test that recitations_count includes all READY recitations for qiraah"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]

        # Asim should have 2 recitations (Hafs + Qaloon)
        asim_item = next(item for item in items if item["name"] == "Test Asim")
        self.assertEqual(2, asim_item["recitations_count"])

        # Nafi should have 1 recitation (Warsh)
        nafi_item = next(item for item in items if item["name"] == "Test Nafi")
        self.assertEqual(1, nafi_item["recitations_count"])

    def test_list_qiraahs_response_schema(self):
        """Test that response contains all required fields"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        self.assertEqual(
            [
                {
                    "id": self.qiraah_asim.id,
                    "name": "Test Asim",
                    "slug": "test-asim",
                    "is_active": True,
                    "riwayahs_count": 2,
                    "recitations_count": 2,
                },
                {
                    "id": self.qiraah_nafi.id,
                    "name": "Test Nafi",
                    "slug": "test-nafi",
                    "is_active": True,
                    "riwayahs_count": 1,
                    "recitations_count": 1,
                },
            ],
            items,
        )

    def test_list_qiraahs_search_by_name(self):
        """Test searching qiraahs by name"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/?search=Asim")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        qiraah_names = {item["name"] for item in items}
        self.assertIn("Test Asim", qiraah_names)

    def test_list_qiraahs_search_by_slug(self):
        """Test searching qiraahs by slug"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/?search=nafi")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        qiraah_names = {item["name"] for item in items}
        self.assertIn("Test Nafi", qiraah_names)

    def test_list_qiraahs_search_case_insensitive(self):
        """Test that search is case-insensitive"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/?search=ASIM")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        qiraah_names = {item["name"] for item in items}
        self.assertIn("Test Asim", qiraah_names)

    def test_list_qiraahs_ordering_by_name(self):
        """Test that qiraahs can be ordered by name"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/?ordering=name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names), names)

    def test_list_qiraahs_ordering_desc(self):
        """Test reverse ordering by name"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/qiraahs/?ordering=-name")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        names = [item["name"] for item in items]
        self.assertEqual(sorted(names, reverse=True), names)

    def test_list_qiraahs_recitations_count_excludes_draft(self):
        """Test that recitations_count doesn't include draft resources"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)
        # Add a draft asset to Asim Qiraah
        draft_resource = baker.make(
            Resource,
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.DRAFT,
        )
        baker.make(
            Asset,
            category=Resource.CategoryChoice.RECITATION,
            riwayah=self.riwayah_hafs,
            resource=draft_resource,
            reciter=self.reciter,
        )

        # Act
        response = self.client.get("/tenant/qiraahs/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()["results"]
        asim_item = next(item for item in items if item["name"] == "Test Asim")
        # Should still be 2 (draft not counted)
        self.assertEqual(2, asim_item["recitations_count"])
