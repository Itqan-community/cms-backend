from django.db.models import Q

from apps.content.models import Asset, CategoryChoice, ContentIssueReport, Qiraah, Reciter, StatusChoice
from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class IssueReportUnitTests(BaseTestCase):
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

        self.repo = IssueReportRepository()
        self.service = IssueReportService(self.repo)

    def test_model_validation_when_data_is_not_correct_should_raise_validation_error(self):
        """Test model validation rules"""
        report = ContentIssueReport(
            reporter=self.user,
            asset=self.asset,
            description="Valid description of the issue.",
        )
        report.full_clean()
        report.save()

        invalid_report = ContentIssueReport(
            reporter=self.user,
            asset=self.asset,
            description="Short",
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            invalid_report.full_clean()

    def test_repository_crud(self):
        """Test repository create, list, get, update, delete"""
        report = self.repo.create_issue_report(
            reporter=self.user,
            asset=self.asset,
            description="Repository test issue",
        )

        self.assertEqual(ContentIssueReport.StatusChoice.PENDING, report.status)
        self.assertEqual(self.asset, report.asset)

        self.assertEqual(1, self.repo.list_issue_reports_qs().count())

        fetched = self.repo.get_issue_report_by_id(report.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(report.id, fetched.id)

        updated = self.repo.update_issue_report(report, status=ContentIssueReport.StatusChoice.RESOLVED)
        self.assertEqual(ContentIssueReport.StatusChoice.RESOLVED, updated.status)

        updated = self.repo.update_issue_report(report, description="Updated description text here.")
        self.assertEqual("Updated description text here.", updated.description)

        self.repo.delete_issue_report(report)
        self.assertEqual(0, self.repo.list_issue_reports_qs().count())

    def test_repository_filtering(self):
        """Test repository filtering"""
        asset2 = Asset.objects.create(
            name="Asset 2",
            publisher=self.publisher,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            file_size="5 MB",
            format="mp3",
            reciter=self.reciter,
            qiraah=self.qiraah,
        )
        report1 = self.repo.create_issue_report(
            reporter=self.user,
            asset=self.asset,
            description="Report 1 description",
            status=ContentIssueReport.StatusChoice.PENDING,
        )
        report2 = self.repo.create_issue_report(
            reporter=self.staff_user,
            asset=asset2,
            description="Report 2 description",
            status=ContentIssueReport.StatusChoice.RESOLVED,
        )

        qs_status = self.repo.list_issue_reports_qs(filters={"status__in": ["pending"]})
        self.assertEqual(1, qs_status.count())
        self.assertEqual(report1.id, qs_status.first().id)

        qs_asset = self.repo.list_issue_reports_qs(filters={"asset": self.asset})
        self.assertEqual(1, qs_asset.count())

        qs_all = self.repo.list_issue_reports_qs()
        self.assertEqual(2, qs_all.count())
        self.assertIsNotNone(report2)

    def test_service_creation(self):
        """Test service creation logic"""
        report = self.service.create_issue_report(
            reporter=self.user,
            asset_id=self.asset.id,
            description="<p>Unsafe description</p> but valid length.",
        )
        self.assertEqual("Unsafe description but valid length.", report.description)
        self.assertEqual(self.asset, report.asset)

        with self.assertRaises(ItqanError) as ctx:
            self.service.create_issue_report(
                reporter=self.user,
                asset_id=self.asset.id,
                description="<p>Short</p>",
            )
        self.assertEqual("description_too_short", ctx.exception.error_name)
        self.assertEqual(400, ctx.exception.status_code)

        with self.assertRaises(ItqanError) as ctx:
            self.service.create_issue_report(
                reporter=self.user,
                asset_id=9999,
                description="Valid description here.",
            )
        self.assertEqual("asset_not_found", ctx.exception.error_name)
        self.assertEqual(404, ctx.exception.status_code)

    def test_service_update_by_reporter(self):
        """Reporter can update description of their own pending report"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")

        updated = self.service.update_issue_report(
            report_id=report.id,
            user=self.user,
            description="Updated description text here.",
        )
        self.assertEqual("Updated description text here.", updated.description)
        self.assertEqual(ContentIssueReport.StatusChoice.PENDING, updated.status)

    def test_service_update_status_by_reporter_is_ignored(self):
        """Reporters cannot change status — the field is silently ignored"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")

        updated = self.service.update_issue_report(
            report_id=report.id,
            user=self.user,
            status=ContentIssueReport.StatusChoice.RESOLVED,
        )
        self.assertEqual(ContentIssueReport.StatusChoice.PENDING, updated.status)

    def test_service_update_non_pending_report_by_reporter_raises_itqan_error(self):
        """Reporters cannot update non-pending reports"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")
        self.repo.update_issue_report(report, status=ContentIssueReport.StatusChoice.UNDER_REVIEW)

        with self.assertRaises(ItqanError) as ctx:
            self.service.update_issue_report(
                report_id=report.id,
                user=self.user,
                description="New description.",
            )
        self.assertEqual("report_not_editable", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_service_update_other_users_report_raises_itqan_error(self):
        """Reporter cannot update another reporter's report"""
        other_user = User.objects.create_user(email="other@example.com", password="password123")
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")

        with self.assertRaises(ItqanError) as ctx:
            self.service.update_issue_report(
                report_id=report.id,
                user=other_user,
                description="Hijacked description.",
            )
        self.assertEqual("permission_denied", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_service_update_by_staff_can_change_status(self):
        """Staff can update status and description on any report"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")
        self.repo.update_issue_report(report, status=ContentIssueReport.StatusChoice.UNDER_REVIEW)

        updated = self.service.update_issue_report(
            report_id=report.id,
            user=self.staff_user,
            status=ContentIssueReport.StatusChoice.RESOLVED,
            description="Staff corrected description.",
        )
        self.assertEqual(ContentIssueReport.StatusChoice.RESOLVED, updated.status)
        self.assertEqual("Staff corrected description.", updated.description)

    def test_service_delete_by_reporter(self):
        """Reporter can delete their own pending report"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Report to be deleted.")
        self.service.delete_issue_report(report_id=report.id, user=self.user)
        self.assertIsNone(self.repo.get_issue_report_by_id(report.id))

    def test_service_delete_non_pending_report_by_reporter_raises_itqan_error(self):
        """Reporter cannot delete non-pending reports"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")
        self.repo.update_issue_report(report, status=ContentIssueReport.StatusChoice.RESOLVED)

        with self.assertRaises(ItqanError) as ctx:
            self.service.delete_issue_report(report_id=report.id, user=self.user)
        self.assertEqual("report_not_editable", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_service_delete_other_users_report_raises_itqan_error(self):
        """Reporter cannot delete another reporter's report"""
        other_user = User.objects.create_user(email="other2@example.com", password="password123")
        report = self.service.create_issue_report(self.user, self.asset.id, "Original description text.")

        with self.assertRaises(ItqanError) as ctx:
            self.service.delete_issue_report(report_id=report.id, user=other_user)
        self.assertEqual("permission_denied", ctx.exception.error_name)
        self.assertEqual(403, ctx.exception.status_code)

    def test_service_delete_by_staff(self):
        """Staff can delete any report regardless of status"""
        report = self.service.create_issue_report(self.user, self.asset.id, "Report to be deleted.")
        self.repo.update_issue_report(report, status=ContentIssueReport.StatusChoice.RESOLVED)

        self.service.delete_issue_report(report_id=report.id, user=self.staff_user)
        self.assertIsNone(self.repo.get_issue_report_by_id(report.id))

    def test_service_publisher_filtering(self):
        """Test service publisher filtering logic"""
        publisher2 = Publisher.objects.create(name="Publisher 2")
        asset2 = Asset.objects.create(
            name="Asset 2",
            publisher=publisher2,
            status=StatusChoice.READY,
            category=CategoryChoice.RECITATION,
            file_size="5 MB",
            format="mp3",
            reciter=self.reciter,
            qiraah=self.qiraah,
        )

        report1 = self.service.create_issue_report(self.user, self.asset.id, "Report 1 desc")
        report2 = self.service.create_issue_report(self.user, asset2.id, "Report 2 desc")

        qs = self.service.get_issue_reports(publisher_q=Q(publisher=self.publisher))
        self.assertEqual(1, qs.count())
        self.assertIsNotNone(report2)
        self.assertEqual(report1.id, qs.first().id)
