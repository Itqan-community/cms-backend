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
        payload = {"asset_id": self.asset.id, "description": "Tenant API Report"}

        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("Tenant API Report", data["description"])
        self.assertEqual(self.asset.id, data["asset_id"])

    def test_create_unauthenticated_returns_401(self):
        self.authenticate_user(None, domain=self.domain)
        payload = {"asset_id": self.asset.id, "description": "Anon Report"}

        response = self.client.post("/tenant/issue-reports/", payload, format="json")

        self.assertEqual(401, response.status_code)

    # --- List ---

    def test_list_issue_reports_tenant_filtering(self):
        """Tenant API only returns reports scoped to the tenant's publisher assets"""
        self._create_report()
        self._create_report(asset=self.asset2, description="Other Publisher Report")
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get("/tenant/issue-reports/")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(1, len(data["results"]))
        self.assertEqual("Tenant Report", data["results"][0]["description"])

    # --- Retrieve ---

    def test_get_issue_report_by_id(self):
        report = self._create_report()
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get(f"/tenant/issue-reports/{report.id}/")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(report.id, data["id"])
        self.assertEqual(self.asset.id, data["asset_id"])

    def test_get_issue_report_not_found_returns_404(self):
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.get("/tenant/issue-reports/9999/")

        self.assertEqual(404, response.status_code)

    # --- Update ---

    def test_update_own_pending_report_description(self):
        report = self._create_report()
        self.authenticate_user(self.user, domain=self.domain)
        payload = {"description": "Updated description text here."}

        response = self.client.patch(f"/tenant/issue-reports/{report.id}/", payload, format="json")

        self.assertEqual(200, response.status_code)
        self.assertEqual("Updated description text here.", response.json()["description"])

    def test_update_non_pending_report_returns_403(self):
        report = self._create_report(status="resolved")
        self.authenticate_user(self.user, domain=self.domain)
        payload = {"description": "Trying to update resolved report."}

        response = self.client.patch(f"/tenant/issue-reports/{report.id}/", payload, format="json")

        self.assertEqual(403, response.status_code)

    def test_update_other_users_report_returns_403(self):
        other_user = User.objects.create_user(email="other@example.com", password="password123")
        report = self._create_report(user=other_user)
        self.authenticate_user(self.user, domain=self.domain)
        payload = {"description": "Hijacking someone else's report."}

        response = self.client.patch(f"/tenant/issue-reports/{report.id}/", payload, format="json")

        self.assertEqual(403, response.status_code)

    # --- Delete ---

    def test_delete_own_pending_report(self):
        report = self._create_report()
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.delete(f"/tenant/issue-reports/{report.id}/")

        self.assertEqual(204, response.status_code)
        self.assertFalse(ContentIssueReport.objects.filter(id=report.id).exists())

    def test_delete_non_pending_report_returns_403(self):
        report = self._create_report(status="resolved")
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.delete(f"/tenant/issue-reports/{report.id}/")

        self.assertEqual(403, response.status_code)

    def test_delete_other_users_report_returns_403(self):
        other_user = User.objects.create_user(email="other2@example.com", password="password123")
        report = self._create_report(user=other_user)
        self.authenticate_user(self.user, domain=self.domain)

        response = self.client.delete(f"/tenant/issue-reports/{report.id}/")

        self.assertEqual(403, response.status_code)

    def test_delete_unauthenticated_returns_401(self):
        report = self._create_report()
        self.authenticate_user(None, domain=self.domain)

        response = self.client.delete(f"/tenant/issue-reports/{report.id}/")

        self.assertEqual(401, response.status_code)
