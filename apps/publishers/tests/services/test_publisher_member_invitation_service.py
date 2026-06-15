import hashlib
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.utils import timezone
from model_bakery import baker

from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService
from apps.users.models import User


class InvitationServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PublisherMemberInvitationService()
        self.publisher = baker.make(Publisher, name="P1")
        self.inviter = baker.make(User, name="Inviter")
        Group.objects.get_or_create(name="Publisher Member Admin")

    def _create(self, email="new@example.com", role=PublisherMember.RoleChoice.STAFF, publisher=None):
        publisher = publisher or self.publisher
        with (
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay") as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            member, inv, raw = self.service.create_invitation(
                publisher=publisher, email=email, role=role, invited_by=self.inviter
            )
        return member, inv, raw, mock_delay

    def test_create_provisions_inactive_user_pending_member_and_invitation(self):
        member, inv, raw, mock_delay = self._create()
        self.assertEqual(PublisherMember.StatusChoice.PENDING, member.status)
        self.assertFalse(member.user.is_active)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.PENDING, inv.status)
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), inv.token_hash)
        mock_delay.assert_called_once_with(inv.id, raw)

    def test_create_existing_active_member_of_same_publisher_conflicts(self):
        existing = baker.make(User, email="dup@example.com", is_active=True)
        PublisherMember.objects.create(
            user=existing,
            publisher=self.publisher,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        with self.assertRaises(ItqanError) as ctx:
            self._create(email="dup@example.com")
        self.assertEqual("already_a_member", ctx.exception.error_name)

    def test_create_existing_member_of_another_publisher_is_allowed(self):
        existing = baker.make(User, email="multi@example.com", is_active=True)
        other_pub = baker.make(Publisher)
        PublisherMember.objects.create(
            user=existing,
            publisher=other_pub,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        member, inv, raw, mock_delay = self._create(email="multi@example.com")
        self.assertEqual(self.publisher.id, member.publisher_id)
        self.assertEqual(PublisherMember.StatusChoice.PENDING, member.status)
        mock_delay.assert_called_once()

    def test_create_duplicate_pending_supersedes_prior_with_new_row(self):
        _, inv1, raw1, _ = self._create(email="again@example.com")
        _, inv2, raw2, mock_delay = self._create(email="again@example.com")
        self.assertNotEqual(inv1.id, inv2.id)
        inv1.refresh_from_db()
        self.assertEqual(PublisherMemberInvitation.StatusChoice.CANCELLED, inv1.status)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.PENDING, inv2.status)
        self.assertNotEqual(raw1, raw2)
        mock_delay.assert_called_once()
        self.assertEqual(
            1,
            PublisherMemberInvitation.objects.filter(
                member=inv2.member, status=PublisherMemberInvitation.StatusChoice.PENDING
            ).count(),
        )

    def test_old_token_is_dead_after_resend(self):
        _, inv1, raw1, _ = self._create(email="rotate@example.com")
        _, _, raw2, _ = self._create(email="rotate@example.com")
        with self.assertRaises(ItqanError) as ctx:
            self.service.accept_invitation(raw1)
        self.assertEqual("invalid_invitation", ctx.exception.error_name)

    def test_accept_admin_activates_sets_password_and_grants_perms(self):
        member, inv, raw, _ = self._create(email="newbie@example.com", role=PublisherMember.RoleChoice.ADMIN)
        with (
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay") as mock_ack,
            self.captureOnCommitCallbacks(execute=True),
        ):
            accepted = self.service.accept_invitation(raw)
        accepted.member.refresh_from_db()
        accepted.member.user.refresh_from_db()
        self.assertEqual(PublisherMember.StatusChoice.ACTIVE, accepted.member.status)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.ACCEPTED, accepted.status)
        self.assertTrue(accepted.member.user.is_active)
        self.assertTrue(accepted.member.user.has_usable_password())
        self.assertTrue(accepted.member.user.groups.filter(name="Publisher Member Admin").exists())
        mock_ack.assert_called_once()

    def test_accept_staff_activates_but_grants_no_perms(self):
        member, inv, raw, _ = self._create(email="grunt@example.com", role=PublisherMember.RoleChoice.STAFF)
        with (
            self.captureOnCommitCallbacks(execute=True),
            patch("apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"),
        ):
            accepted = self.service.accept_invitation(raw)
        accepted.member.refresh_from_db()
        accepted.member.user.refresh_from_db()
        self.assertEqual(PublisherMember.StatusChoice.ACTIVE, accepted.member.status)
        self.assertTrue(accepted.member.user.is_active)
        self.assertFalse(accepted.member.user.groups.filter(name="Publisher Member Admin").exists())
        self.assertFalse(accepted.member.user.has_perm("portal_view_publisher_members"))

    def test_accept_is_single_use(self):
        _, _, raw, _ = self._create(email="once@example.com")
        with self.captureOnCommitCallbacks(execute=True):
            self.service.accept_invitation(raw)
        with self.assertRaises(ItqanError) as ctx:
            self.service.accept_invitation(raw)
        self.assertEqual("invalid_invitation", ctx.exception.error_name)

    def test_accept_expired_rejected(self):
        _, inv, raw, _ = self._create(email="late@example.com")
        PublisherMemberInvitation.objects.filter(pk=inv.id).update(
            expires_at=timezone.now() - timezone.timedelta(days=1)
        )
        with self.assertRaises(ItqanError) as ctx:
            self.service.accept_invitation(raw)
        self.assertEqual("invalid_invitation", ctx.exception.error_name)
