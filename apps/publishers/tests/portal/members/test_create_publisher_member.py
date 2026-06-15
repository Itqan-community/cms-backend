from unittest.mock import patch

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.users.models import User


class CreateMemberTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        Group.objects.get_or_create(name="Publisher Member Admin")
        self.publisher = baker.make(Publisher)
        self.admin = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.admin,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.url = "/portal/members/"

    def _post(self, **body):
        body.setdefault("publisher_id", self.publisher.id)
        with (
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay") as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(self.url, data=body, content_type="application/json")
        return resp, mock_delay

    def test_invite_member_returns_201_and_sends_invite(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, mock_delay = self._post(name="New Staff", email="staff@example.com", role="staff")
        self.assertEqual(201, resp.status_code, resp.content)
        body = resp.json()
        self.assertEqual("staff@example.com", body["email"])
        self.assertEqual("pending", body["status"])
        self.assertIn("expires_at", body)
        member = PublisherMember.objects.get(id=body["id"])
        self.assertEqual(self.publisher.id, member.publisher_id)
        self.assertTrue(PublisherMemberInvitation.objects.filter(member=member).exists())
        mock_delay.assert_called_once()

    def test_invite_admin_role_needs_only_invite_perm(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, _ = self._post(name="Boss", email="boss@example.com", role="admin")
        self.assertEqual(201, resp.status_code, resp.content)

    def test_invite_without_permission_returns_403(self):
        self.authenticate_user(self.admin)
        resp, _ = self._post(name="X", email="x@example.com", role="staff")
        self.assertEqual(403, resp.status_code, resp.content)

    def test_admin_cannot_invite_in_other_publisher_returns_403(self):
        other = baker.make(Publisher)
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, _ = self._post(publisher_id=other.id, name="X", email="x@example.com", role="staff")
        self.assertEqual(403, resp.status_code, resp.content)
