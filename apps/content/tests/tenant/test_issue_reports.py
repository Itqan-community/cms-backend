from apps.content.models import Asset, CategoryChoice, ContentIssueReport, Qiraah, Reciter, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class IssueReportTenantApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.domain = Domain.objects.create(domain="tenant.example.com", publisher=self.publisher, is_primary=True)

        self.user = User.objects.create_user(email="reporter@example.com", password="password123")

        # Create dependencies for Asset
        self.reciter = Reciter.objects.create(name="Test Reciter")
        self.qiraah = Qiraah.objects.create(name="Test Qiraah")

        self.asset = Asset.objects.create(
            name="Test Asset",
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            file_size="10 MB",
            format="mp3",
            reciter=self.reciter,
            qiraah=self.qiraah,
        )

        # Another publisher's asset
        self.publisher2 = Publisher.objects.create(name="Other Publisher")
        self.asset2 = Asset.objects.create(
            name="Other Asset",
            publisher=self.publisher2,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            file_size="10 MB",
            format="mp3",
            reciter=self.reciter,
            qiraah=self.qiraah,
        )

    def test_create_issue_report_tenant_with_correct_data_should_return_201(self):
        """Test creating an issue report via tenant API"""
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)
        payload = {
            "content_type": "asset",
            "content_id": self.asset.id,
            "description": "Tenant API Report",
        }

        # Act
        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        # Assert
        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("Tenant API Report", data["description"])
        self.assertEqual(self.asset.id, data["object_id"])

    def test_create_unauthenticated(self):
        """Test creating report without auth fails"""
        # Arrange
        self.authenticate_user(None, domain=self.domain)
        payload = {
            "content_type": "asset",
            "content_id": self.asset.id,
            "description": "Anon Report",
        }

        # Act
        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        # Assert
        self.assertEqual(401, response.status_code)

    def test_list_issue_reports_tenant_filtering(self):
        """Test tenant API only lists reports for tenant's publisher content"""
        # Arrange
        ContentIssueReport.objects.create(
            reporter=self.user,
            content_object=self.asset,
            description="Tenant Report",
            status="pending",
        )
        ContentIssueReport.objects.create(
            reporter=self.user,
            content_object=self.asset2,
            description="Other Publisher Report",
            status="pending",
        )
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/issue-reports/")

        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(1, len(data["results"]))
        self.assertEqual("Tenant Report", data["results"][0]["description"])
