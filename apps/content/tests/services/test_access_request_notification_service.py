from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.access_request_notification_service import AccessRequestNotificationService
from apps.core.services.email import email_service
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User

_SEND_EMAIL = "apps.content.services.access_request_notification_service.email_service.send_email"


def _make_asset(publisher: Publisher) -> Asset:
    return Asset.objects.create(
        name="Test Asset",
        publisher=publisher,
        status=StatusChoice.READY,
        category=CategoryChoice.MUSHAF,
        license=LicenseChoice.CC0,
        file_size="1 MB",
        format="pdf",
        description="desc",
        language="en",
    )


class AccessRequestNotificationServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = AccessRequestNotificationService(AssetAccessRequestRepository())
        self.publisher = baker.make(Publisher, contact_email="")
        self.developer = baker.make(User)
        self.asset = _make_asset(self.publisher)

    def _make_request(self, status=AssetAccessRequest.StatusChoice.PENDING, asset=None, **kwargs):
        return AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=asset or self.asset,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
            status=status,
            **kwargs,
        )

    # --- developer outcome email ---

    def test_send_developer_outcome_email_approved_uses_accepted_template(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.APPROVED)

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_developer_outcome_email(req.id)

        mock_send.assert_called_once()
        _args, kwargs = mock_send.call_args
        self.assertEqual("emails/access_request_accepted.html", kwargs["template"])
        self.assertEqual([self.developer.email], kwargs["recipients"])

    def test_send_developer_outcome_email_rejected_uses_rejected_template(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.REJECTED, rejection_reason="not eligible")

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_developer_outcome_email(req.id)

        mock_send.assert_called_once()
        _args, kwargs = mock_send.call_args
        self.assertEqual("emails/access_request_rejected.html", kwargs["template"])
        self.assertEqual("not eligible", kwargs["context"]["rejection_reason"])

    def test_send_developer_outcome_email_pending_does_not_send(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.PENDING)

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_developer_outcome_email(req.id)

        mock_send.assert_not_called()

    def test_send_developer_outcome_email_missing_request_does_not_raise(self):
        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_developer_outcome_email(999999)

        mock_send.assert_not_called()

    # --- pending access requests notification ---

    def test_notify_publishers_of_pending_requests_where_multiple_pending_across_publishers_should_send_one_email_per_publisher(
        self,
    ):
        # Arrange
        self.publisher.contact_email = "publisher-a@example.com"
        self.publisher.save(update_fields=["contact_email"])
        publisher_b = baker.make(Publisher, contact_email="publisher-b@example.com")
        asset_b = _make_asset(publisher_b)

        self._make_request()
        self._make_request()
        self._make_request()
        self._make_request(asset=asset_b)

        # Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        self.assertEqual(2, mock_send.call_count)
        counts = sorted(call.kwargs["context"]["count"] for call in mock_send.call_args_list)
        self.assertEqual([1, 3], counts)

    def test_notify_publishers_of_pending_requests_where_no_pending_should_not_send(self):
        # Arrange / Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        mock_send.assert_not_called()

    def test_notify_publishers_of_pending_requests_where_publisher_has_no_contact_email_should_skip(self):
        # Arrange
        self.publisher.contact_email = ""
        self.publisher.save(update_fields=["contact_email"])
        self._make_request()

        # Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        mock_send.assert_not_called()

    def test_notify_publishers_of_pending_requests_where_request_auto_accepted_should_be_excluded(self):
        # Arrange
        self.publisher.contact_email = "publisher@example.com"
        self.publisher.save(update_fields=["contact_email"])
        self._make_request(status=AssetAccessRequest.StatusChoice.APPROVED)

        # Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        mock_send.assert_not_called()

    def test_notify_publishers_of_pending_requests_where_request_old_but_still_pending_should_be_included(self):
        # Arrange
        from datetime import timedelta

        from django.utils import timezone

        self.publisher.contact_email = "publisher@example.com"
        self.publisher.save(update_fields=["contact_email"])
        req = self._make_request()
        AssetAccessRequest.objects.filter(id=req.id).update(created_at=timezone.now() - timedelta(days=5))

        # Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        mock_send.assert_called_once()
        self.assertEqual(1, mock_send.call_args.kwargs["context"]["count"])

    def test_notify_publishers_of_pending_requests_where_one_publisher_send_fails_should_still_send_others(self):
        # Arrange
        self.publisher.contact_email = "publisher-a@example.com"
        self.publisher.save(update_fields=["contact_email"])
        publisher_b = baker.make(Publisher, contact_email="publisher-b@example.com")
        asset_b = _make_asset(publisher_b)

        self._make_request()
        self._make_request(asset=asset_b)

        # Act
        with patch.object(
            email_service, email_service.send_email.__name__, side_effect=[Exception("boom"), None]
        ) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        self.assertEqual(2, mock_send.call_count)


class AccessRequestNotificationServiceContactEmailTests(BaseTestCase):
    """Kept to exercise the no-contact-email publisher membership path."""

    def setUp(self):
        super().setUp()
        self.service = AccessRequestNotificationService(AssetAccessRequestRepository())
        self.publisher = baker.make(Publisher, contact_email="")
        self.developer = baker.make(User)
        self.asset = _make_asset(self.publisher)

    def test_notify_publishers_of_pending_requests_where_publisher_member_exists_but_no_contact_email_should_skip(
        self,
    ):
        # Arrange
        admin = baker.make(User, email="admin@example.com")
        PublisherMember.objects.create(
            user=admin,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=self.asset,
            developer_access_reason="reason",
            intended_use=AssetAccessRequest.IntendedUseChoice.NON_COMMERCIAL,
            status=AssetAccessRequest.StatusChoice.PENDING,
        )

        # Act
        with patch.object(email_service, email_service.send_email.__name__) as mock_send:
            self.service.notify_publishers_of_pending_requests()

        # Assert
        mock_send.assert_not_called()
