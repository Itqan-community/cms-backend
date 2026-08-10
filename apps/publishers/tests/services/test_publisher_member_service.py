from model_bakery import baker

from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.services.publisher_member_service import PublisherMemberService
from apps.publishers.tests.group_helpers import admin_group, itqan_internal_group, member_group
from apps.users.models import User


class MemberServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PublisherMemberService()
        self.publisher = baker.make(Publisher)

    def _member(self, group=None, status=PublisherMember.StatusChoice.ACTIVE, publisher=None, user=None):
        return PublisherMember.objects.create(
            user=user or baker.make(User),
            publisher=publisher or self.publisher,
            group=group or member_group(),
            status=status,
        )

    def test_update_member_where_group_changed_should_swap_groups(self):
        # Arrange
        member = self._member(group=member_group())
        self.service.grant_member_perms(member)

        # Act
        self.service.update_member(member, fields={"group_id": admin_group().id, "name": "Jane"})

        # Assert
        member.refresh_from_db()
        member.user.refresh_from_db()
        self.assertEqual(admin_group().id, member.group_id)
        self.assertEqual("Jane", member.user.name)
        self.assertTrue(member.user.groups.filter(name="Publisher Member Admin").exists())
        self.assertFalse(member.user.groups.filter(name="Publisher Member").exists())
        self.assertTrue(member.user.has_perm("portal_update_publisher_members"))

    def test_update_member_where_group_is_itqan_internal_should_reject(self):
        # Arrange
        member = self._member(group=member_group())
        self.service.grant_member_perms(member)

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_member(member, fields={"group_id": itqan_internal_group().id})

        # Assert
        self.assertEqual("invalid_group", ctx.exception.error_name)
        member.refresh_from_db()
        self.assertEqual(member_group().id, member.group_id)

    def test_update_member_where_member_pending_should_not_touch_user_groups(self):
        # Arrange
        member = self._member(group=member_group(), status=PublisherMember.StatusChoice.PENDING)

        # Act
        self.service.update_member(member, fields={"group_id": admin_group().id})

        # Assert: the group is recorded, but nothing is granted before acceptance.
        member.refresh_from_db()
        self.assertEqual(admin_group().id, member.group_id)
        self.assertEqual(0, member.user.groups.count())

    def test_update_member_where_user_active_elsewhere_should_keep_shared_group(self):
        # Arrange: one user, two publishers, both on the baseline group.
        user = baker.make(User)
        other_publisher = baker.make(Publisher)
        self._member(group=member_group(), publisher=other_publisher, user=user)
        member = self._member(group=member_group(), user=user)
        user.groups.add(member_group())

        # Act: change only this membership's group.
        self.service.update_member(member, fields={"group_id": admin_group().id})

        # Assert: the baseline group stays because the other membership still needs it.
        user.refresh_from_db()
        self.assertTrue(user.groups.filter(name="Publisher Member").exists())
        self.assertTrue(user.groups.filter(name="Publisher Member Admin").exists())

    def test_grant_member_perms_where_member_has_group_should_apply_only_that_group(self):
        # Arrange
        member = self._member(group=member_group())

        # Act
        self.service.grant_member_perms(member)

        # Assert
        member.user.refresh_from_db()
        self.assertTrue(member.user.groups.filter(name="Publisher Member").exists())
        self.assertFalse(member.user.groups.filter(name="Publisher Member Admin").exists())

    def test_delete_member_where_only_membership_should_remove_group(self):
        # Arrange
        member = self._member(group=member_group())
        self.service.grant_member_perms(member)
        user = member.user

        # Act
        self.service.delete_member(member)

        # Assert
        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name="Publisher Member").exists())

    def test_delete_member_where_user_active_elsewhere_should_keep_shared_group(self):
        # Arrange: same user and group across two publishers.
        user = baker.make(User)
        other_publisher = baker.make(Publisher)
        self._member(group=member_group(), publisher=other_publisher, user=user)
        target = self._member(group=member_group(), user=user)
        user.groups.add(member_group())

        # Act
        self.service.delete_member(target)

        # Assert: removing one membership must not strip access earned by the other.
        user.refresh_from_db()
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
        self.assertTrue(user.groups.filter(name="Publisher Member").exists())

    def test_delete_last_active_member_where_only_member_should_succeed(self):
        # Arrange
        member = self._member()

        # Act
        self.service.delete_member(member)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=member.pk).exists())

    def test_delete_active_admin_where_granted_should_revoke_group(self):
        # Arrange
        self._member(group=admin_group())
        target = self._member(group=admin_group())
        self.service.grant_member_perms(target)
        user = target.user

        # Act
        self.service.delete_member(target)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name="Publisher Member Admin").exists())

    def test_delete_non_last_member_ok(self):
        # Arrange
        self._member()
        target = self._member()

        # Act
        self.service.delete_member(target)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
