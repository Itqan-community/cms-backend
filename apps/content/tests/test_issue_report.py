from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.content.models import Asset, ContentIssueReport, Qiraah, Reciter, Resource
from apps.content.repositories.issue_report import IssueReportRepository
from apps.content.services.issue_report import IssueReportService
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User


class IssueReportUnitTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Test Publisher")
        self.user = User.objects.create_user(email="reporter@example.com", password="password123")
        self.staff_user = User.objects.create_user(email="staff@example.com", password="password123", is_staff=True)

        self.resource = Resource.objects.create(
            name="Test Resource",
            publisher=self.publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )

        # Create dependencies for Asset constraint
        self.reciter = Reciter.objects.create(name="Test Reciter")
        self.qiraah = Qiraah.objects.create(name="Test Qiraah")

        # Create proper Asset
        self.asset = Asset.objects.create(
            name="Test Asset",
            resource=self.resource,
            category=Resource.CategoryChoice.RECITATION,
            file_size="10 MB",
            format="mp3",
            reciter=self.reciter,
            qiraah=self.qiraah,
        )

        self.repo = IssueReportRepository()
        self.service = IssueReportService(self.repo)

    def test_model_validation_when_data_is_not_correct_should_raise_validation_error(self):
        """Test model validation rules"""
        # Arrange
        report = ContentIssueReport(
            reporter=self.user,
            content_object=self.resource,
            description="Valid description of the issue.",
        )

        # Act
        report.full_clean()
        report.save()

        # Assert
        # Test short description
        # Arrange
        invalid_report = ContentIssueReport(
            reporter=self.user,
            content_object=self.resource,
            description="Short",
        )

        # Act & Assert
        with self.assertRaises(ValidationError):
            invalid_report.full_clean()

    def test_repository_crud(self):
        """Test repository create, list, get, update"""
        # Arrange
        description = "Repository test issue"

        # Act
        report = self.repo.create_issue_report(
            reporter=self.user,
            content_object=self.resource,
            description=description,
        )

        # Assert
        self.assertEqual(ContentIssueReport.StatusChoice.PENDING, report.status)
        self.assertEqual(self.resource, report.content_object)

        # Act
        qs = self.repo.list_issue_reports_qs()

        # Assert
        self.assertEqual(1, qs.count())

        # Act
        fetched = self.repo.get_issue_report_by_id(report.id)

        # Assert
        self.assertIsNotNone(fetched)
        self.assertEqual(report.id, fetched.id)

        # Act
        updated = self.repo.update_issue_report_status(report, ContentIssueReport.StatusChoice.RESOLVED)

        # Assert
        self.assertEqual(ContentIssueReport.StatusChoice.RESOLVED, updated.status)

    def test_repository_filtering(self):
        """Test repository filtering"""
        # Arrange
        report1 = self.repo.create_issue_report(
            reporter=self.user,
            content_object=self.resource,
            description="Report 1 description",
            status=ContentIssueReport.StatusChoice.PENDING,
        )
        report2 = self.repo.create_issue_report(
            reporter=self.staff_user,
            content_object=self.asset,
            description="Report 2 description",
            status=ContentIssueReport.StatusChoice.RESOLVED,
        )

        # Act
        qs_status = self.repo.list_issue_reports_qs(filters={"status__in": ["pending"]})

        # Assert
        self.assertEqual(1, qs_status.count())
        self.assertEqual(report1.id, qs_status.first().id)

        # Arrange
        content_type_asset = ContentType.objects.get_for_model(Asset)

        # Act
        qs_ctype = self.repo.list_issue_reports_qs(filters={"content_type": content_type_asset})

        # Assert
        self.assertEqual(1, qs_ctype.count())
        self.assertIsNotNone(report2)
        self.assertEqual(report2.id, qs_ctype.first().id)

    def test_service_creation(self):
        """Test service creation logic"""
        # Arrange
        description = "<p>Unsafe description</p> but valid length."
        expected_description = "Unsafe description but valid length."

        # Act
        report = self.service.create_issue_report(
            reporter=self.user,
            content_type="resource",
            content_id=self.resource.id,
            description=description,
        )

        # Assert
        self.assertEqual(expected_description, report.description)
        self.assertEqual(self.resource, report.content_object)

        # Arrange
        short_description = "<p>Short</p>"

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.service.create_issue_report(
                reporter=self.user,
                content_type="resource",
                content_id=self.resource.id,
                description=short_description,
            )

        # Arrange
        invalid_id = 9999

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.service.create_issue_report(
                reporter=self.user,
                content_type="resource",
                content_id=invalid_id,
                description="Valid description",
            )

    def test_service_publisher_filtering(self):
        """Test service publisher filtering logic"""
        # Arrange
        publisher2 = Publisher.objects.create(name="Publisher 2")
        resource2 = Resource.objects.create(
            name="Res 2", publisher=publisher2, category=Resource.CategoryChoice.RECITATION
        )

        report1 = self.service.create_issue_report(self.user, "resource", self.resource.id, "Report 1 desc")
        report2 = self.service.create_issue_report(self.user, "resource", resource2.id, "Report 2 desc")

        # Filter for self.publisher
        publisher_q = Q(publisher=self.publisher)

        # Act
        qs = self.service.get_issue_reports(publisher_q=publisher_q)

        # Assert
        self.assertEqual(1, qs.count())
        self.assertIsNotNone(report2)
        self.assertEqual(report1.id, qs.first().id)
