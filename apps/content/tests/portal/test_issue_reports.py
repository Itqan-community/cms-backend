from unittest.mock import patch

from django.contrib.auth.models import Group

from apps.content.models import Asset, CategoryChoice, ContentIssueReport, Qiraah, Reciter, StatusChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User

_NOTIFY = "apps.content.services.issue_report_notifications.IssueReportNotificationService.notify_status_changed"


class IssueReportPortalApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.user = User.objects.create_user(email="reporter@example.com", password="password123")
        self.staff_user = User.objects.create_user(email="staff@example.com", password="password123", is_staff=True)

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

    def _create_report(self, description="Existing report description.", status="pending"):
        return ContentIssueReport.objects.create(
            reporter=self.user,
            asset=self.asset,
            description=description,
            status=status,
        )

    # --- Create ---

    def test_create_issue_report_with_correct_data_should_return_201(self):
        self.authenticate_user(self.staff_user)
        payload = {"asset_id": self.asset.id, "description": "API Test Issue Report"}

        response = self.client.post("/portal/issue-reports/", payload, format="json")

        self.assertEqual(201, response.status_code)
        data = response.json()
        self.assertEqual("API Test Issue Report", data["description"])
        self.assertEqual(self.asset.id, data["asset_id"])

    def test_create_issue_report_with_invalid_asset_id_should_return_404(self):
        self.authenticate_user(self.staff_user)
        payload = {"asset_id": 9999, "description": "Report for nonexistent asset"}

        response = self.client.post("/portal/issue-reports/", payload, format="json")

        self.assertEqual(404, response.status_code)

    # --- List ---

    def test_list_issue_reports(self):
        self._create_report()
        self.authenticate_user(self.staff_user)

        response = self.client.get("/portal/issue-reports/")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(1, len(data["results"]))
        self.assertEqual("Existing report description.", data["results"][0]["description"])

    def test_list_issue_reports_filter_by_status(self):
        self._create_report(status="pending")
        self._create_report(description="Resolved report description.", status="resolved")
        self.authenticate_user(self.staff_user)

        response = self.client.get("/portal/issue-reports/?status=pending")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(1, len(data["results"]))
        self.assertEqual("pending", data["results"][0]["status"])

    # --- Retrieve ---

    def test_get_issue_report_by_id(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)

        response = self.client.get(f"/portal/issue-reports/{report.id}/")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual(report.id, data["id"])
        self.assertEqual(self.asset.id, data["asset_id"])

    def test_get_issue_report_not_found_returns_404(self):
        self.authenticate_user(self.staff_user)

        response = self.client.get("/portal/issue-reports/9999/")

        self.assertEqual(404, response.status_code)

    # --- Update ---

    def test_update_issue_report_description_by_staff(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)
        payload = {"description": "Staff updated description text."}

        response = self.client.patch(f"/portal/issue-reports/{report.id}/", payload, format="json")

        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertEqual("Staff updated description text.", data["description"])

    def test_update_issue_report_status_by_staff(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)
        payload = {"status": "resolved"}

        response = self.client.patch(f"/portal/issue-reports/{report.id}/", payload, format="json")

        self.assertEqual(200, response.status_code)
        self.assertEqual("resolved", response.json()["status"])

    def test_update_issue_report_not_found_returns_404(self):
        self.authenticate_user(self.staff_user)

        response = self.client.patch("/portal/issue-reports/9999/", {"status": "resolved"}, format="json")

        self.assertEqual(404, response.status_code)

    # --- Delete ---

    def test_delete_issue_report_by_staff(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)

        response = self.client.delete(f"/portal/issue-reports/{report.id}/")

        self.assertEqual(204, response.status_code)
        self.assertFalse(ContentIssueReport.objects.filter(id=report.id).exists())

    def test_delete_issue_report_not_found_returns_404(self):
        self.authenticate_user(self.staff_user)

        response = self.client.delete("/portal/issue-reports/9999/")

        self.assertEqual(404, response.status_code)

    def test_delete_resolved_report_by_staff_succeeds(self):
        """Staff can delete reports in any status"""
        report = self._create_report(status="resolved")
        self.authenticate_user(self.staff_user)

        response = self.client.delete(f"/portal/issue-reports/{report.id}/")

        self.assertEqual(204, response.status_code)

    # --- Notifications ---

    def test_patch_status_change_calls_notification_service(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)

        with patch(_NOTIFY) as mock_notify:
            response = self.client.patch(f"/portal/issue-reports/{report.id}/", {"status": "resolved"}, format="json")

        self.assertEqual(200, response.status_code)
        mock_notify.assert_called_once_with(report.id, "pending", "resolved")

    def test_patch_description_only_does_not_call_notification_service(self):
        report = self._create_report()
        self.authenticate_user(self.staff_user)

        with patch(_NOTIFY) as mock_notify:
            response = self.client.patch(
                f"/portal/issue-reports/{report.id}/", {"description": "Updated description text."}, format="json"
            )

        self.assertEqual(200, response.status_code)
        mock_notify.assert_not_called()

    def test_patch_same_status_does_not_call_notification_service(self):
        report = self._create_report()  # default status: pending
        self.authenticate_user(self.staff_user)

        with patch(_NOTIFY) as mock_notify:
            response = self.client.patch(f"/portal/issue-reports/{report.id}/", {"status": "pending"}, format="json")

        self.assertEqual(200, response.status_code)
        mock_notify.assert_not_called()


class IssueReportPortalPublisherScopeTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Own Publisher")
        self.other_publisher = Publisher.objects.create(name="Other Publisher")
        self.member = User.objects.create_user(email="member@example.com", password="password123")
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            group=Group.objects.create(name="Own Publisher role"),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.staff_user = User.objects.create_user(email="staff@example.com", password="password123", is_staff=True)
        reciter = Reciter.objects.create(name="Test Reciter")
        qiraah = Qiraah.objects.create(name="Test Qiraah")
        own_asset = self._asset(self.publisher, reciter, qiraah)
        other_asset = self._asset(self.other_publisher, reciter, qiraah)
        self.own_report = self._report(own_asset, "Report on our own asset.")
        self.other_report = self._report(other_asset, "Report on another publisher's asset.")

    def _asset(self, publisher: Publisher, reciter: Reciter, qiraah: Qiraah) -> Asset:
        return Asset.objects.create(
            name=f"{publisher.name} asset",
            publisher=publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            file_size="10 MB",
            format="mp3",
            reciter=reciter,
            qiraah=qiraah,
        )

    def _report(self, asset: Asset, description: str) -> ContentIssueReport:
        return ContentIssueReport.objects.create(
            reporter=self.member, asset=asset, description=description, status="pending"
        )

    def test_list_issue_reports_where_member_selects_own_publisher_should_exclude_other_publishers(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get("/portal/issue-reports/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([self.own_report.id], [row["id"] for row in response.json()["results"]])

    def test_list_issue_reports_where_staff_without_tenant_should_return_every_publisher(self):
        # Arrange
        self.authenticate_user(self.staff_user)

        # Act
        response = self.client.get("/portal/issue-reports/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual({self.own_report.id, self.other_report.id}, {row["id"] for row in response.json()["results"]})

    def test_get_issue_report_where_report_is_on_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(f"/portal/issue-reports/{self.other_report.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])

    def test_update_issue_report_where_report_is_on_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.patch(
            f"/portal/issue-reports/{self.other_report.id}/",
            {"description": "Edited across publishers."},
            format="json",
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])
        self.other_report.refresh_from_db()
        self.assertEqual("Report on another publisher's asset.", self.other_report.description)

    def test_delete_issue_report_where_report_is_on_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.delete(f"/portal/issue-reports/{self.other_report.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])
        self.assertTrue(ContentIssueReport.objects.filter(id=self.other_report.id).exists())

    def test_create_issue_report_where_no_tenant_should_allow_any_publishers_asset(self):
        # Arrange — gallery consumers report on any asset without X-Tenant
        self.authenticate_user(self.member)
        payload = {"asset_id": self.other_report.asset_id, "description": "Consumer report from the gallery."}

        # Act
        response = self.client.post("/portal/issue-reports/", payload, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
