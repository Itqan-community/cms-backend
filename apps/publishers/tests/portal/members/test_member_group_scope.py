from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
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
        self.authenticate_user(self.admin, HTTP_X_TENANT=str(self.publisher.id))

    def _member(self, email: str) -> PublisherMember:
        return PublisherMember.objects.create(
            user=baker.make(User, email=email),
            publisher=self.publisher,
            group=self.editors,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_invite_with_other_publishers_group_is_400_invalid_group(self):
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

        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])

    def test_move_member_to_other_publishers_group_is_400_invalid_group(self):
        member = self._member("m@example.com")

        resp = self.client.patch(
            f"/portal/members/{member.id}/", data={"group_id": self.foreign.id}, content_type="application/json"
        )

        self.assertEqual(400, resp.status_code, resp.content)
        self.assertEqual("invalid_group", resp.json()["error_name"])
        member.refresh_from_db()
        self.assertEqual(self.editors.id, member.group_id)

    def test_member_list_shows_display_name(self):
        self._member("m@example.com")

        resp = self.client.get("/portal/members/")

        self.assertEqual(200, resp.status_code, resp.content)
        self.assertEqual({"Editors"}, {item["group_name"] for item in resp.json()["results"]})

    def test_member_list_query_count_does_not_grow_with_members(self):
        def count() -> int:
            with CaptureQueriesContext(connection) as ctx:
                resp = self.client.get("/portal/members/")
            self.assertEqual(200, resp.status_code, resp.content)
            return len(ctx.captured_queries)

        self._member("m1@example.com")
        count()  # warm per-process caches (content types) so only per-row queries differ
        two = count()
        for i in range(4):
            self._member(f"more{i}@example.com")

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

    def test_invitation_email_uses_display_name(self):
        invitation = self._invitation()

        with patch("apps.publishers.services.publisher_member_notification_service.email_service.send_email") as send:
            PublisherMemberNotificationService().send_invitation_email(invitation.id, "raw-token")

        self.assertEqual("Editors", send.call_args.kwargs["context"]["group_name"])

    def test_invitation_group_name_uses_display_name(self):
        self.assertEqual("Editors", self._invitation().group_name)
