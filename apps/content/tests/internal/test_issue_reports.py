from apps.content.models import Asset, CategoryChoice, ContentIssueReport, Qiraah, Reciter, StatusChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class IssueReportInternalApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.user = User.objects.create_user(email="reporter@example.com", password="password123")
        self.staff_user = User.objects.create_user(email="staff@example.com", password="password123", is_staff=True)

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

    def test_create_issue_report_with_correct_data_should_return_201(self):
        """Test creating an issue report via internal API"""
        # Arrange
        self.authenticate_user(self.staff_user)
        payload = {
            "content_type": "asset",
            "content_id": self.asset.id,
            "description": "API Test Issue Report",
        }

        # Act
        response = self.client.post("/cms-api/issue-reports/", payload, format="json")

        # Assert
        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("API Test Issue Report", data["description"])
        self.assertEqual(self.asset.id, data["object_id"])

    def test_list_issue_reports(self):
        """Test listing issue reports via internal API"""
        # Arrange
        ContentIssueReport.objects.create(
            reporter=self.user,
            content_object=self.asset,
            description="Existing Report",
            status="pending",
        )
        self.authenticate_user(self.staff_user)

        # Act
        response = self.client.get("/cms-api/issue-reports/")

        # Assert
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(1, len(data["results"]))
        self.assertEqual("Existing Report", data["results"][0]["description"])
