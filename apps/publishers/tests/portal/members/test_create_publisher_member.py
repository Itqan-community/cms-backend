from unittest.mock import patch

from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.tests.group_helpers import admin_group, itqan_internal_group, member_group
from apps.users.models import User


class CreateMemberTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.admin = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.admin,
            publisher=self.publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.url = "/portal/members/"

    def _post(self, **body):
        body.setdefault("publisher_id", self.publisher.id)
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ) as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(self.url, data=body, content_type="application/json")
        return resp, mock_delay

    def test_invite_member_returns_201_and_sends_invite(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, mock_delay = self._post(name="New Staff", email="staff@example.com", group_id=member_group().id)
        self.assertEqual(201, resp.status_code, resp.content)
        body = resp.json()
        self.assertEqual("New Staff", body["name"])
        self.assertEqual("staff@example.com", body["email"])
        self.assertEqual("pending", body["status"])
        self.assertIn("expires_at", body)
        member = PublisherMember.objects.get(id=body["id"])
        self.assertEqual(self.publisher.id, member.publisher_id)
        self.assertEqual("New Staff", member.user.name)
        self.assertTrue(PublisherMemberInvitation.objects.filter(member=member).exists())
        mock_delay.assert_called_once()

    def test_invite_existing_user_keeps_existing_name(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        existing = baker.make(User, email="existing@example.com", name="Original Name")
        resp, _ = self._post(name="Different Name", email="existing@example.com", group_id=member_group().id)
        self.assertEqual(201, resp.status_code, resp.content)
        existing.refresh_from_db()
        self.assertEqual("Original Name", existing.name)

    def test_invite_member_where_admin_group_should_need_only_invite_perm(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, _ = self._post(name="Boss", email="boss@example.com", group_id=admin_group().id)
        self.assertEqual(201, resp.status_code, resp.content)

    def test_invite_without_permission_returns_403(self):
        self.authenticate_user(self.admin)
        resp, _ = self._post(name="X", email="x@example.com", group_id=member_group().id)
        self.assertEqual(403, resp.status_code, resp.content)

    def test_admin_cannot_invite_in_other_publisher_returns_403(self):
        other = baker.make(Publisher)
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        resp, _ = self._post(publisher_id=other.id, name="X", email="x@example.com", group_id=member_group().id)
        self.assertEqual(403, resp.status_code, resp.content)

    def test_invite_member_where_group_is_itqan_internal_should_return_400(self):
        # Arrange
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        internal = itqan_internal_group()

        # Act
        resp, mock_delay = self._post(name="Sneaky", email="sneaky@example.com", group_id=internal.id)

        # Assert
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])
        self.assertFalse(PublisherMember.objects.filter(user__email="sneaky@example.com").exists())
        mock_delay.assert_not_called()

    def test_invite_member_where_group_unknown_should_return_400(self):
        # Arrange
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)

        # Act
        resp, _ = self._post(name="Ghost", email="ghost@example.com", group_id=10_000_000)

        # Assert
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])

    def test_invite_member_where_group_valid_should_persist_group_and_echo_it(self):
        # Arrange
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        group = admin_group()

        # Act
        resp, _ = self._post(name="Boss", email="boss2@example.com", group_id=group.id)

        # Assert
        self.assertEqual(201, resp.status_code, resp.content)
        body = resp.json()
        self.assertEqual(group.id, body["group_id"])
        self.assertEqual(group.name, body["group_name"])
        self.assertEqual(group.id, PublisherMember.objects.get(id=body["id"]).group_id)

    def test_invite_member_where_group_id_missing_should_return_400(self):
        # Arrange
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)

        # Act: group_id is required now that the role literal is gone.
        resp, _ = self._post(name="NoGroup", email="nogroup@example.com")

        # Assert
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("validation_error", resp.json()["error_name"])
