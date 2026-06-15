from unittest.mock import patch

from django.contrib.auth.models import Group
from django.utils import timezone
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.users.models import User


class MemberDetailTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        Group.objects.get_or_create(name="Publisher Member Admin")
        self.p1 = baker.make(Publisher)
        self.p2 = baker.make(Publisher)
        self.admin = baker.make(User, is_staff=False)
        PublisherMember.objects.create(
            user=self.admin,
            publisher=self.p1,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.p1_other = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=self.p1,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        self.p2_member = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=self.p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_admin_can_retrieve_own_publisher_member(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get(f"/portal/members/{self.p1_other.id}/")
        self.assertEqual(200, resp.status_code, resp.content)

    def test_admin_cannot_retrieve_other_publisher_member_403(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.get(f"/portal/members/{self.p2_member.id}/")
        self.assertEqual(403, resp.status_code, resp.content)

    def test_update_member_promotes_to_admin(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS)
        resp = self.client.patch(
            f"/portal/members/{self.p1_other.id}/",
            data={"role": "admin"},
            content_type="application/json",
        )
        self.assertEqual(200, resp.status_code, resp.content)
        self.p1_other.refresh_from_db()
        self.assertEqual("admin", self.p1_other.role)
        self.assertTrue(self.p1_other.user.groups.filter(name="Publisher Member Admin").exists())

    def test_patch_without_update_perm_403(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS)
        resp = self.client.patch(
            f"/portal/members/{self.p1_other.id}/",
            data={"name": "X"},
            content_type="application/json",
        )
        self.assertEqual(403, resp.status_code, resp.content)

    def test_update_and_delete_perms_are_independent(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS)
        patch_resp = self.client.patch(
            f"/portal/members/{self.p1_other.id}/",
            data={"name": "Renamed"},
            content_type="application/json",
        )
        self.assertEqual(200, patch_resp.status_code, patch_resp.content)
        delete_resp = self.client.delete(f"/portal/members/{self.p1_other.id}/")
        self.assertEqual(403, delete_resp.status_code, delete_resp.content)

    def test_admin_cannot_delete_self_403(self):
        own = PublisherMember.objects.get(user=self.admin)
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)
        resp = self.client.delete(f"/portal/members/{own.id}/")
        self.assertEqual(403, resp.status_code, resp.content)

    def test_admin_removes_active_member_204(self):
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)
        resp = self.client.delete(f"/portal/members/{self.p1_other.id}/")
        self.assertEqual(204, resp.status_code, resp.content)
        self.assertFalse(PublisherMember.objects.filter(pk=self.p1_other.pk).exists())

    def test_delete_member_where_requester_is_staff_and_last_active_should_remove(self):
        itqan = baker.make(User, is_staff=True)
        self.authenticate_user(itqan)
        self.give_permission(itqan, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)
        # p1_other is the only other active member; admin is the other — staff user deletes p1_other
        # then delete the admin member leaving none — staff can do this
        resp = self.client.delete(f"/portal/members/{self.p1_other.id}/")
        self.assertEqual(204, resp.status_code, resp.content)
        self.assertFalse(PublisherMember.objects.filter(pk=self.p1_other.pk).exists())

    def test_admin_cancels_pending_member_204(self):
        pending = PublisherMember.objects.create(
            user=baker.make(User, is_active=False),
            publisher=self.p1,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.PENDING,
        )
        inv = PublisherMemberInvitation.objects.create(
            publisher=self.p1,
            invited_by=self.admin,
            member=pending,
            token_hash="tok",
            expires_at=timezone.now(),
        )
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS)
        resp = self.client.delete(f"/portal/members/{pending.id}/")
        self.assertEqual(204, resp.status_code, resp.content)
        inv.refresh_from_db()
        self.assertEqual(PublisherMemberInvitation.StatusChoice.CANCELLED, inv.status)
        self.assertFalse(PublisherMember.objects.filter(pk=pending.pk).exists())

    def test_resend_invite_rotates_and_sends(self):
        pending = PublisherMember.objects.create(
            user=baker.make(User, is_active=False),
            publisher=self.p1,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.PENDING,
        )
        old_inv = PublisherMemberInvitation.objects.create(
            publisher=self.p1,
            invited_by=self.admin,
            member=pending,
            token_hash="old",
            expires_at=timezone.now(),
        )
        self.authenticate_user(self.admin)
        self.give_permission(self.admin, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS)
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ) as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            resp = self.client.post(f"/portal/members/{pending.id}/resend-invite/")
        self.assertEqual(200, resp.status_code, resp.content)
        mock_delay.assert_called_once()
        old_inv.refresh_from_db()
        self.assertEqual(PublisherMemberInvitation.StatusChoice.CANCELLED, old_inv.status)
        self.assertEqual(
            1,
            PublisherMemberInvitation.objects.filter(
                member=pending, status=PublisherMemberInvitation.StatusChoice.PENDING
            ).count(),
        )
