from unittest.mock import patch

from model_bakery import baker

from apps.content.models import Asset, AssetAccessRequest, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.repositories.access_request import AssetAccessRequestRepository
from apps.content.services.access_request_notification_service import AccessRequestNotificationService
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

    def _make_request(self, status=AssetAccessRequest.StatusChoice.PENDING, **kwargs):
        return AssetAccessRequest.objects.create(
            developer_user=self.developer,
            asset=self.asset,
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

    # --- publisher new-request email ---

    def test_send_publisher_new_request_email_uses_contact_email(self):
        self.publisher.contact_email = "publisher@example.com"
        self.publisher.save(update_fields=["contact_email"])
        req = self._make_request()

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_publisher_new_request_email(req.id)

        _args, kwargs = mock_send.call_args
        self.assertEqual(["publisher@example.com"], kwargs["recipients"])
        self.assertEqual("emails/access_request_new.html", kwargs["template"])
        self.assertFalse(kwargs["context"]["auto_accepted"])

    def test_send_publisher_new_request_email_skips_when_no_contact_email(self):
        admin = baker.make(User, email="admin@example.com")
        PublisherMember.objects.create(
            user=admin,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        req = self._make_request()

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_publisher_new_request_email(req.id)

        mock_send.assert_not_called()

    def test_send_publisher_new_request_email_auto_accepted_flag_true(self):
        req = self._make_request(status=AssetAccessRequest.StatusChoice.APPROVED)
        self.publisher.contact_email = "publisher@example.com"
        self.publisher.save(update_fields=["contact_email"])

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_publisher_new_request_email(req.id)

        _args, kwargs = mock_send.call_args
        self.assertTrue(kwargs["context"]["auto_accepted"])

    def test_send_publisher_new_request_email_no_recipients_does_not_raise(self):
        req = self._make_request()

        with patch(_SEND_EMAIL) as mock_send:
            self.service.send_publisher_new_request_email(req.id)

        mock_send.assert_not_called()
