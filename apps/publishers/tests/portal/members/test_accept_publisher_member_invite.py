from unittest.mock import patch

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService
from apps.users.models import User


class AcceptInviteTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        Group.objects.get_or_create(name="Publisher Member Admin")
        self.publisher = baker.make(Publisher)

    def _invite(self, email="acceptme@example.com"):
        with (
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            member, inv, raw = PublisherMemberInvitationService().create_invitation(
                publisher=self.publisher,
                email=email,
                role="staff",
                invited_by=baker.make(User),
            )
        return member, inv, raw

    def test_accept_activates_member_no_auth_required(self):
        member, inv, raw = self._invite()
        with (
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(f"/portal/invitations/{raw}/accept/")
        self.assertEqual(200, resp.status_code, resp.content)
        member.refresh_from_db()
        self.assertEqual("active", member.status)

    def test_accept_invalid_token_returns_400(self):
        resp = self.client.post("/portal/invitations/not-a-real-token/accept/")
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_invitation", resp.json()["error_name"])
