from unittest.mock import patch

from django.core import mail
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.publisher_member_notification_service import PublisherMemberNotificationService
from apps.publishers.tests.group_helpers import publisher_role
from apps.users.models import User


class MemberGroupScopeTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.other = baker.make(Publisher)
        self.editors = publisher_role(self.publisher, "Editors")
        self.foreign = publisher_role(self.other, "Editors")
        self.admin = baker.make(User, email="admin@example.com")
        for permission in (
            PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS,
            PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS,
            PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS,
        ):
            self.give_permission(self.admin, permission)
        PublisherMember.objects.create(
            user=self.admin, publisher=self.publisher, group=self.editors, status=PublisherMember.StatusChoice.ACTIVE
        )

    def _member(self, email: str) -> PublisherMember:
        return PublisherMember.objects.create(
            user=baker.make(User, email=email),
            publisher=self.publisher,
            group=self.editors,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_invite_member_where_group_belongs_to_other_publisher_should_return_400(self):
        # Arrange
        self.authenticate_user(self.admin, HTTP_X_TENANT=str(self.publisher.id))
        with patch(
            "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
        ):
            resp = self.client.post(
                "/portal/members/",
                data={
                    "publisher_id": self.publisher.id,
                    "name": "New",
                    "email": "new@example.com",
                    "group_id": self.foreign.id,
                },
                content_type="application/json",
            )

        # Act & Assert
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])

    def test_update_member_where_group_belongs_to_other_publisher_should_return_400(self):
        # Arrange
        self.authenticate_user(self.admin, HTTP_X_TENANT=str(self.publisher.id))
        member = self._member("m@example.com")

        # Act
        resp = self.client.patch(
            f"/portal/members/{member.id}/", data={"group_id": self.foreign.id}, content_type="application/json"
        )

        # Assert
        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])
        member.refresh_from_db()
        self.assertEqual(self.editors.id, member.group_id)

    def test_list_members_where_role_named_should_return_display_name(self):
        # Arrange
        self.authenticate_user(self.admin, HTTP_X_TENANT=str(self.publisher.id))
        self._member("m@example.com")

        # Act
        resp = self.client.get("/portal/members/")

        # Assert
        self.assertEqual(200, resp.status_code, resp.content)
        self.assertEqual({"Editors"}, {item["group_name"] for item in resp.json()["results"]})

    def test_list_members_where_more_members_should_keep_query_count(self):
        # Arrange
        self.authenticate_user(self.admin, HTTP_X_TENANT=str(self.publisher.id))

        def count() -> int:
            with CaptureQueriesContext(connection) as ctx:
                resp = self.client.get("/portal/members/")
            self.assertEqual(200, resp.status_code, resp.content)
            return len(ctx.captured_queries)

        # Act
        self._member("m1@example.com")
        count()  # warm per-process caches (content types) so only per-row queries differ
        two = count()
        for i in range(4):
            self._member(f"more{i}@example.com")

        # Assert
        self.assertEqual(two, count())

    def _invitation(self) -> PublisherMemberInvitation:
        member = PublisherMember.objects.create(
            user=baker.make(User, email="invited@example.com"), publisher=self.publisher, group=self.editors
        )
        return PublisherMemberInvitation.objects.create(
            publisher=self.publisher,
            member=member,
            invited_by=self.admin,
            token_hash="a" * 64,
            expires_at=timezone.now() + timezone.timedelta(days=3),
        )

    def test_send_invitation_email_where_role_named_should_use_display_name(self):
        # Arrange
        invitation = self._invitation()

        # Act
        with patch("apps.publishers.services.publisher_member_notification_service.email_service.send_email") as send:
            PublisherMemberNotificationService().send_invitation_email(invitation.id, "raw-token")

        # Assert
        self.assertEqual("Editors", send.call_args.kwargs["context"]["group_name"])

    def test_send_invitation_email_where_invitee_prefers_arabic_should_use_arabic_role_name(self):
        # Arrange
        PublisherGroup.objects.filter(group=self.editors).update(name_ar="المحررون")
        invitation = self._invitation()
        User.objects.filter(email="invited@example.com").update(preferred_language="ar")

        # Act
        PublisherMemberNotificationService().send_invitation_email(invitation.id, "raw-token")

        # Assert
        self.assertEqual(1, len(mail.outbox))
        self.assertIn("المحررون", mail.outbox[0].alternatives[0][0])

    def test_invitation_group_name_where_role_named_should_return_display_name(self):
        # Arrange, Act & Assert
        self.assertEqual("Editors", self._invitation().group_name)
