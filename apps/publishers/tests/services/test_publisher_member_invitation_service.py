import hashlib
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.utils import timezone
from model_bakery import baker

from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember, PublisherMemberInvitation
from apps.publishers.services.effective_permissions import effective_permissions
from apps.publishers.services.publisher_member_invitation_service import PublisherMemberInvitationService
from apps.publishers.tests.group_helpers import admin_group, itqan_internal_group, member_group
from apps.users.models import User


class InvitationServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PublisherMemberInvitationService()
        self.publisher = baker.make(Publisher, name="P1")
        self.inviter = baker.make(User, name="Inviter")
        Group.objects.get_or_create(name="Publisher Member Admin")

    def _create(self, email="new@example.com", group=None, publisher=None):
        publisher = publisher or self.publisher
        group = group or member_group(publisher=self.publisher)
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_invitation_email.delay"
            ) as mock_delay,
            self.captureOnCommitCallbacks(execute=True),
        ):
            member, inv, raw = self.service.create_invitation(
                publisher=publisher, email=email, group_id=group.id, invited_by=self.inviter
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
            group=member_group(publisher=self.publisher),
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
            group=member_group(publisher=self.publisher),
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
        member, inv, raw, _ = self._create(
            email="newbie@example.com",
            group=admin_group(PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS, publisher=self.publisher),
        )
        with (
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ) as mock_ack,
            self.captureOnCommitCallbacks(execute=True),
        ):
            accepted = self.service.accept_invitation(raw)
        accepted.member.refresh_from_db()
        accepted.member.user.refresh_from_db()
        self.assertEqual(PublisherMember.StatusChoice.ACTIVE, accepted.member.status)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.ACCEPTED, accepted.status)
        self.assertTrue(accepted.member.user.is_active)
        self.assertTrue(accepted.member.user.has_usable_password())
        # The member's chosen group applies through the membership; user.groups is untouched.
        self.assertIn(
            PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS.value,
            effective_permissions(accepted.member.user, accepted.member.publisher),
        )
        self.assertEqual(0, accepted.member.user.groups.count())
        mock_ack.assert_called_once()

    def test_accept_staff_activates_with_read_baseline_only(self):
        member, inv, raw, _ = self._create(
            email="grunt@example.com",
            group=member_group(
                PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_VIEW_PUBLISHER_MEMBERS, publisher=self.publisher
            ),
        )
        with (
            self.captureOnCommitCallbacks(execute=True),
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ),
        ):
            accepted = self.service.accept_invitation(raw)
        accepted.member.refresh_from_db()
        accepted.member.user.refresh_from_db()
        user = accepted.member.user
        self.assertEqual(PublisherMember.StatusChoice.ACTIVE, accepted.member.status)
        self.assertTrue(user.is_active)
        perms = effective_permissions(user, accepted.member.publisher)
        self.assertIn("portal_access", perms)
        self.assertIn("portal_view_publisher_members", perms)
        self.assertNotIn("portal_invite_publisher_members", perms)

    def test_create_invitation_where_group_is_itqan_internal_should_reject(self):
        # Arrange
        internal = itqan_internal_group()

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self._create(email="sneaky@example.com", group=internal)

        # Assert
        self.assertEqual("invalid_group", ctx.exception.error_name)
        self.assertFalse(PublisherMember.objects.filter(user__email="sneaky@example.com").exists())

    def test_create_invitation_where_group_does_not_exist_should_reject(self):
        # Arrange
        missing_group_id = 10_000_000

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.create_invitation(
                publisher=self.publisher,
                email="ghost@example.com",
                group_id=missing_group_id,
                invited_by=self.inviter,
            )

        # Assert
        self.assertEqual("invalid_group", ctx.exception.error_name)

    def test_create_invitation_where_member_pending_with_other_group_should_update_group(self):
        # Arrange
        member, _, _, _ = self._create(email="changed@example.com", group=member_group(publisher=self.publisher))
        self.assertEqual(member_group(publisher=self.publisher).id, member.group_id)

        # Act
        updated, _, _, _ = self._create(email="changed@example.com", group=admin_group(publisher=self.publisher))

        # Assert
        updated.refresh_from_db()
        self.assertEqual(member.id, updated.id)
        self.assertEqual(admin_group(publisher=self.publisher).id, updated.group_id)

    def test_accept_where_member_belongs_to_another_publisher_should_keep_both_roles(self):
        # Arrange: same user is already an active admin at another publisher.
        user = baker.make(User, email="multi2@example.com", is_active=True)
        other_publisher = baker.make(Publisher)
        PublisherMember.objects.create(
            user=user,
            publisher=other_publisher,
            group=admin_group(PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS, publisher=self.publisher),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        _, _, raw, _ = self._create(
            email="multi2@example.com",
            group=member_group(PermissionChoice.PORTAL_READ_RECITER, publisher=self.publisher),
        )

        # Act
        with (
            self.captureOnCommitCallbacks(execute=True),
            patch(
                "apps.publishers.services.publisher_member_invitation_service.send_publisher_member_activated_email.delay"
            ),
        ):
            self.service.accept_invitation(raw)

        # Assert: each publisher keeps its own role.
        user = User.objects.get(id=user.id)
        self.assertIn("portal_update_publisher_members", effective_permissions(user, other_publisher))
        self.assertNotIn("portal_read_reciter", effective_permissions(user, other_publisher))
        new_publisher = PublisherMember.objects.exclude(publisher=other_publisher).get(user=user).publisher
        self.assertIn("portal_read_reciter", effective_permissions(user, new_publisher))

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

    def test_resend_where_member_is_none_should_raise_invalid_invitation(self):
        # Arrange: a pending invitation whose member row was deleted (member_id -> NULL).
        member, inv, _, _ = self._create(email="orphan-resend@example.com")
        member.delete()
        inv.refresh_from_db()
        self.assertIsNone(inv.member_id)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.PENDING, inv.status)

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.resend(inv, self.inviter)

        # Assert
        self.assertEqual("invalid_invitation", ctx.exception.error_name)
        self.assertEqual(400, ctx.exception.status_code)

    def test_cancel_where_member_is_none_should_raise_invalid_invitation(self):
        # Arrange: a pending invitation whose member row was deleted (member_id -> NULL).
        member, inv, _, _ = self._create(email="orphan-cancel@example.com")
        member.delete()
        inv.refresh_from_db()
        self.assertIsNone(inv.member_id)
        self.assertEqual(PublisherMemberInvitation.StatusChoice.PENDING, inv.status)

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.cancel(inv, self.inviter)

        # Assert
        self.assertEqual("invalid_invitation", ctx.exception.error_name)
        self.assertEqual(400, ctx.exception.status_code)
