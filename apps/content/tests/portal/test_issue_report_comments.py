from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core import mail
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from apps.content.models import (
    Asset,
    CategoryChoice,
    ContentIssueReport,
    ContentIssueReportComment,
    Qiraah,
    Reciter,
    StatusChoice,
)
from apps.content.services.issue_report_notifications import IssueReportNotificationService
from apps.content.tasks import send_issue_comment_email
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class IssueReportCommentPortalApiTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = Publisher.objects.create(name="Own Publisher")
        self.other_publisher = Publisher.objects.create(name="Other Publisher")
        self.member = User.objects.create_user(email="member@example.com", password="password123", name="Member")
        PublisherMember.objects.create(
            user=self.member,
            publisher=self.publisher,
            group=Group.objects.create(name="Own Publisher role"),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.reporter = User.objects.create_user(email="reporter@example.com", password="password123", name="Reporter")
        reciter = Reciter.objects.create(name="Test Reciter")
        qiraah = Qiraah.objects.create(name="Test Qiraah")
        self.report = self._report(self._asset(self.publisher, reciter, qiraah))
        self.other_report = self._report(self._asset(self.other_publisher, reciter, qiraah))

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

    def _report(self, asset: Asset) -> ContentIssueReport:
        return ContentIssueReport.objects.create(
            reporter=self.reporter, asset=asset, description="The ayah audio is cut short.", status="pending"
        )

    def _url(self, report: ContentIssueReport) -> str:
        return f"/portal/issue-reports/{report.id}/comments/"

    def test_create_issue_report_comment_where_member_posts_on_own_publisher_report_should_store_it(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.post(self._url(self.report), {"body": "  Thanks, <b>fixing</b> it.  "}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        data = response.json()
        self.assertEqual("Thanks, fixing it.", data["body"])
        self.assertEqual({"id": self.member.id, "name": "Member", "is_reporter": False}, data["author"])
        comment = ContentIssueReportComment.objects.get(id=data["id"])
        self.assertEqual(
            (self.report.id, self.member.id, "Thanks, fixing it."), (comment.report_id, comment.author_id, comment.body)
        )
        self.assertIsNotNone(comment.created_at)

    def test_create_issue_report_comment_where_body_is_only_markup_should_return_400(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.post(self._url(self.report), {"body": " <p> </p> "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("comment_empty", response.json()["error_name"])
        self.assertFalse(ContentIssueReportComment.objects.exists())

    def test_create_issue_report_comment_where_body_exceeds_2000_characters_should_return_400(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.post(self._url(self.report), {"body": "x" * 2001}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("comment_too_long", response.json()["error_name"])

    def test_create_issue_report_comment_where_report_is_on_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.post(self._url(self.other_report), {"body": "Not ours."}, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])
        self.assertFalse(ContentIssueReportComment.objects.exists())

    def test_create_issue_report_comment_where_user_is_not_a_member_should_return_404(self):
        # Arrange — the reporter is not a publisher member, so the portal shows them no report
        self.authenticate_user(self.reporter)

        # Act
        response = self.client.post(self._url(self.report), {"body": "Any news?"}, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])

    def test_list_issue_report_comments_where_thread_has_comments_should_return_them_oldest_first(self):
        # Arrange
        first = ContentIssueReportComment.objects.create(report=self.report, author=self.member, body="First")
        second = ContentIssueReportComment.objects.create(report=self.report, author=self.reporter, body="Second")
        ContentIssueReportComment.objects.create(report=self.other_report, author=self.reporter, body="Elsewhere")
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(self._url(self.report))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual([first.id, second.id], [row["id"] for row in data])
        self.assertEqual([False, True], [row["author"]["is_reporter"] for row in data])
        self.assertNotIn("email", data[1]["author"])

    def test_list_issue_report_comments_where_author_account_is_deleted_should_keep_comment_without_author(self):
        # Arrange
        leaver = User.objects.create_user(email="leaver@example.com", password="password123")
        comment = ContentIssueReportComment.objects.create(report=self.report, author=leaver, body="Old reply")
        leaver.delete()
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(self._url(self.report))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            [{"id": comment.id, "author": None, "body": "Old reply"}],
            [{k: row[k] for k in ("id", "author", "body")} for row in response.json()],
        )

    def test_list_issue_report_comments_where_report_is_on_other_publisher_should_return_404(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(self._url(self.other_report))

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("report_not_found", response.json()["error_name"])

    def test_list_issue_report_comments_where_thread_grows_should_not_add_queries(self):
        # Arrange
        ContentIssueReportComment.objects.create(report=self.report, author=self.member, body="One")
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))
        self.client.get(self._url(self.report))  # warms the X-Tenant publisher cache
        with CaptureQueriesContext(connection) as one_comment:
            self.client.get(self._url(self.report))
        for i in range(5):
            ContentIssueReportComment.objects.create(report=self.report, author=self.reporter, body=f"More {i}")

        # Act
        with CaptureQueriesContext(connection) as six_comments:
            response = self.client.get(self._url(self.report))

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(6, len(response.json()))
        self.assertEqual(len(one_comment.captured_queries), len(six_comments.captured_queries))

    def test_create_issue_report_comment_where_member_posts_should_email_the_reporter_after_commit(self):
        # Arrange
        self.authenticate_user(self.member, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        with (
            patch.object(send_issue_comment_email, send_issue_comment_email.delay.__name__) as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(self._url(self.report), {"body": "We fixed the audio."}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        delay.assert_called_once_with(response.json()["id"])

    def test_create_issue_report_comment_where_reporter_comments_on_own_report_should_not_email(self):
        # Arrange — the reporter is also a member of the publisher
        PublisherMember.objects.create(
            user=self.reporter,
            publisher=self.publisher,
            group=Group.objects.create(name="Reporter role"),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.authenticate_user(self.reporter, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        with (
            patch.object(send_issue_comment_email, send_issue_comment_email.delay.__name__) as delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(self._url(self.report), {"body": "Adding a detail."}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertTrue(response.json()["author"]["is_reporter"])
        delay.assert_not_called()

    @override_settings(FRONTEND_BASE_URL="https://fanar.example")
    def test_notify_comment_added_where_comment_exists_should_email_reporter_without_author_address(self):
        # Arrange
        self.reporter.preferred_language = "en"
        self.reporter.save(update_fields=["preferred_language"])
        comment = ContentIssueReportComment.objects.create(
            report=self.report, author=self.member, body="Fixed in the next version."
        )

        # Act
        IssueReportNotificationService().notify_comment_added(comment.id)

        # Assert
        self.assertEqual(1, len(mail.outbox))
        message = mail.outbox[0]
        html = message.alternatives[0][0]
        self.assertEqual(["reporter@example.com"], message.to)
        self.assertEqual("New reply on your issue report for Own Publisher asset", message.subject)
        self.assertIn("Fixed in the next version.", html)
        self.assertIn("Own Publisher", html)
        self.assertIn(f"https://fanar.example/gallery/asset/{self.report.asset_id}", html)
        self.assertNotIn("member@example.com", html)

    def test_notify_comment_added_where_comment_is_missing_should_send_nothing(self):
        # Arrange
        missing_id = 999999

        # Act
        IssueReportNotificationService().notify_comment_added(missing_id)

        # Assert
        self.assertEqual(0, len(mail.outbox))
