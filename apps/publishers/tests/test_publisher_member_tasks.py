from unittest.mock import patch

from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.publisher_member_notification_service import PublisherMemberNotificationService
from apps.publishers.tasks import send_publisher_member_activated_email, send_publisher_member_invitation_email
from apps.users.models import User


class MemberTasksTest(BaseTestCase):
    def _invitation(self):
        publisher = baker.make(Publisher, name="Tafsir Center")
        user = baker.make(User, email="invitee@example.com")
        member = PublisherMember.objects.create(user=user, publisher=publisher, role=PublisherMember.RoleChoice.STAFF)
        return PublisherMemberInvitation.objects.create(
            publisher=publisher,
            invited_by=baker.make(User, name="Boss"),
            member=member,
            token_hash="h",
            expires_at=timezone.now(),
        )

    def test_invitation_task_delegates_to_notification_service(self):
        inv = self._invitation()
        with patch.object(PublisherMemberNotificationService, "send_invitation_email") as mock_send:
            send_publisher_member_invitation_email(inv.id, "rawtoken123")
            mock_send.assert_called_once_with(inv.id, "rawtoken123")

    def test_activation_task_delegates_to_notification_service(self):
        inv = self._invitation()
        with patch.object(PublisherMemberNotificationService, "send_activation_email") as mock_send:
            send_publisher_member_activated_email(inv.member.id, "GenPass123")
            mock_send.assert_called_once_with(inv.member.id, "GenPass123")

    @patch("apps.publishers.services.publisher_member_notification_service.email_service.send_email")
    def test_notification_service_sends_invitation_email_with_correct_template(self, mock_send):
        inv = self._invitation()
        PublisherMemberNotificationService().send_invitation_email(inv.id, "rawtoken123")
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(["invitee@example.com"], kwargs["recipients"])
        self.assertEqual("emails/publisher_member_invitation.html", kwargs["template"])
        self.assertIn("rawtoken123", kwargs["context"]["accept_url"])

    @patch("apps.publishers.services.publisher_member_notification_service.email_service.send_email")
    def test_notification_service_sends_activation_email_with_password(self, mock_send):
        inv = self._invitation()
        PublisherMemberNotificationService().send_activation_email(inv.member.id, "GenPass123")
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual("emails/publisher_member_activated.html", kwargs["template"])
        self.assertEqual("GenPass123", kwargs["context"]["password"])
