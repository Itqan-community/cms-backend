from apps.content.models import Asset, CategoryChoice, ContentIssueReport, Qiraah, Reciter, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Domain, Publisher
from apps.users.models import User


class IssueReportTenantApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.domain = Domain.objects.create(domain="tenant.example.com", publisher=self.publisher, is_primary=True)
        self.user = User.objects.create_user(email="reporter@example.com", password="password123")

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

    def _create_report(self, asset=None, user=None, description="Tenant Report", status="pending"):
        return ContentIssueReport.objects.create(
            reporter=user or self.user,
            asset=asset or self.asset,
            description=description,
            status=status,
        )

    # --- Create ---

    def test_create_issue_report_tenant_with_correct_data_should_return_201(self):
        self.authenticate_user(self.user, domain=self.domain)
        payload = {"asset_id": self.asset.id, "description": "Tenant API Report", "context": {"surah": 1, "ayah": 1}}

        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("Tenant API Report", data["description"])
        self.assertEqual(self.asset.id, data["asset_id"])

    def test_create_issue_report_tenant_where_context_given_should_validate_and_return_it(self):
        # Arrange
        self.authenticate_user(self.user, domain=self.domain)
        valid = {"asset_id": self.asset.id, "description": "Tenant API Report", "context": {"surah": 2, "ayah": 255}}
        invalid = {"asset_id": self.asset.id, "description": "Tenant API Report", "context": {"surah": 2, "ayah": 287}}
        missing = {"asset_id": self.asset.id, "description": "Tenant API Report"}

        # Act
        created = self.client.post("/tenant/issue-reports/", valid, format="json")
        rejected = self.client.post("/tenant/issue-reports/", invalid, format="json")
        unlocated = self.client.post("/tenant/issue-reports/", missing, format="json")

        # Assert
        self.assertEqual(201, created.status_code)
        self.assertEqual({"surah": 2, "ayah": 255}, created.json()["context"])
        self.assertEqual("Al-Baqarah 2:255", created.json()["context_label"])
        self.assertEqual(400, rejected.status_code)
        self.assertEqual("invalid_issue_context", rejected.json()["error_name"])
        self.assertEqual(400, unlocated.status_code)
        self.assertEqual("invalid_issue_context", unlocated.json()["error_name"])

    def test_create_unauthenticated_returns_401(self):
        self.authenticate_user(None, domain=self.domain)
        payload = {"asset_id": self.asset.id, "description": "Anon Report", "context": {"surah": 1, "ayah": 1}}

        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        self.assertEqual(401, response.status_code)

    # --- Create only: existing reports are never readable or editable on a tenant domain ---

    def test_list_issue_reports_where_anonymous_on_tenant_domain_should_not_be_served(self):
        # Arrange
        self._create_report()
        self.authenticate_user(None, domain=self.domain)

        # Act
        response = self.client.get("/tenant/issue-reports/")

        # Assert
        self.assertEqual(405, response.status_code, response.content)
        self.assertNotIn(b"Tenant Report", response.content)

    def test_list_issue_reports_where_signed_in_on_tenant_domain_should_not_be_served(self):
        # Arrange
        self._create_report()
        self.authenticate_user(self.user, domain=self.domain)

        # Act
        response = self.client.get("/tenant/issue-reports/")

        # Assert
        self.assertEqual(405, response.status_code, response.content)
        self.assertNotIn(b"Tenant Report", response.content)

    def test_issue_report_detail_where_any_method_should_not_exist(self):
        # Arrange
        report = self._create_report()
        self.authenticate_user(self.user, domain=self.domain)
        url = f"/tenant/issue-reports/{report.id}/"

        # Act
        responses = {
            "get": self.client.get(url),
            "patch": self.client.patch(url, {"description": "Changed"}, format="json"),
            "delete": self.client.delete(url),
        }

        # Assert
        self.assertEqual({"get": 404, "patch": 404, "delete": 404}, {k: r.status_code for k, r in responses.items()})
        report.refresh_from_db()
        self.assertEqual("Tenant Report", report.description)
