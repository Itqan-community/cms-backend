from unittest.mock import patch

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService
from apps.users.models import User


class AcceptanceCriteriaTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        Group.objects.get_or_create(name="Publisher Member Admin")
        self.p1 = baker.make(Publisher)
        self.admin = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.admin,
            publisher=self.p1,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def _invite_via_service(self, publisher, email, role="staff"):
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            return PublisherMemberInvitationService().create_invitation(
                publisher=publisher, email=email, role=role, invited_by=self.admin
            )

    # AC#5 + AC#1: invite creates pending invitation + sends email (flat endpoint)
    def test_invite_creates_pending_and_emails(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ) as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(
                "/portal/members/",
                data={"publisher_id": self.p1.id, "name": "E1", "email": "e1@example.com", "role": "staff"},
                content_type="application/json",
            )
        self.assertEqual(201, resp.status_code, resp.content)
        member = PublisherMember.objects.get(id=resp.json()["id"])
        inv = PublisherMemberInvitation.objects.filter(member=member, status="pending").first()
        self.assertIsNotNone(inv)
        self.assertEqual("pending", inv.status)
        mock_delay.assert_called_once()

    # AC#6 + AC#2: accept → active member + password set + token unusable. Staff role grants NO perms.
    def test_accept_makes_active_no_perms_for_staff_and_token_single_use(self):
        member, inv, raw = self._invite_via_service(self.p1, "e2@example.com", role="staff")
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(f"/portal/invitations/{raw}/accept/")
        self.assertEqual(200, resp.status_code)
        member.refresh_from_db()
        member.user.refresh_from_db()
        self.assertEqual("active", member.status)
        self.assertTrue(member.user.is_active)
        self.assertTrue(member.user.has_usable_password())
        self.assertFalse(member.user.groups.filter(name="Publisher Member Admin").exists())
        self.assertFalse(member.user.has_perm("portal_view_publisher_members"))
        resp2 = self.client.post(f"/portal/invitations/{raw}/accept/")
        self.assertEqual(400, resp2.status_code)

    # AC#6 admin variant: accept as admin → 4 perms granted
    def test_accept_admin_grants_member_perms(self):
        member, _inv, raw = self._invite_via_service(self.p1, "boss@example.com", role="admin")
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.client.post(f"/portal/invitations/{raw}/accept/")
        member.refresh_from_db()
        member.user.refresh_from_db()
        self.assertTrue(member.user.groups.filter(name="Publisher Member Admin").exists())
        self.assertTrue(member.user.has_perm("portal_update_publisher_members"))
        self.assertTrue(member.user.has_perm("portal_delete_publisher_members"))

    # AC#3: admin cannot manage other publisher's member
    def test_admin_cannot_manage_other_publisher(self):
        p2 = baker.make(Publisher)
        other = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)
        self.assertEqual(403, self.client.get(f"/portal/members/{other.id}/").status_code)
        self.assertEqual(403, self.client.delete(f"/portal/members/{other.id}/").status_code)

    # AC#4: Itqan lists across publishers
    def test_itqan_lists_across_publishers(self):
        p2 = baker.make(Publisher)
        PublisherMember.objects.create(
            user=baker.make(User),
            publisher=p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        itqan = baker.make(User, is_staff=True)
        self.authenticate_user(itqan)
        self.give_permission(itqan, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get("/portal/members/")
        ids = {m["publisher_id"] for m in resp.json()["results"]}
        self.assertTrue({self.p1.id, p2.id}.issubset(ids))

    # email case-insensitive duplicate within same publisher → resend (cancel prior + new row)
    def test_duplicate_email_case_insensitive_resends_one_pending(self):
        _, inv1, _ = self._invite_via_service(self.p1, "Case@Example.com")
        _, inv2, _ = self._invite_via_service(self.p1, "case@example.com")
        self.assertNotEqual(inv1.id, inv2.id)
        self.assertEqual(
            1,
            PublisherMemberInvitation.objects.filter(
                publisher=self.p1, status=PublisherMemberInvitation.StatusChoice.PENDING
            ).count(),
        )

    # re-invite an already-ACTIVE member of P → 409 (spec §7)
    def test_reinvite_active_member_conflicts(self):
        from apps.core.ninja_utils.errors import ItqanError

        member, _inv, raw = self._invite_via_service(self.p1, "active@example.com")
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.client.post(f"/portal/invitations/{raw}/accept/")
        with (
            self.assertRaises(ItqanError) as ctx,
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ),
            self.captureOnCommitCallbacks(execute=True),
        ):
            PublisherMemberInvitationService().create_invitation(
                publisher=self.p1, email="active@example.com", role="staff", invited_by=self.admin
            )
        self.assertEqual("already_a_member", ctx.exception.error_name)
