from model_bakery import baker

from apps.core.ninja_utils.errors import ItqanError
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.services.effective_permissions import effective_permissions
from apps.publishers.services.publisher_member_service import PublisherMemberService
from apps.publishers.tests.group_helpers import admin_group, itqan_internal_group, member_group
from apps.users.models import User

READ = PermissionChoice.PORTAL_READ_RECITER
UPDATE_MEMBERS = PermissionChoice.PORTAL_UPDATE_PUBLISHER_MEMBERS


class MemberServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PublisherMemberService()
        self.publisher = baker.make(Publisher)

    def _member(self, group=None, status=PublisherMember.StatusChoice.ACTIVE, publisher=None, user=None):
        return PublisherMember.objects.create(
            user=user or baker.make(User),
            publisher=publisher or self.publisher,
            group=group or member_group(publisher=self.publisher),
            status=status,
        )

    def _perms(self, user: User, publisher: Publisher) -> frozenset[str]:
        return effective_permissions(User.objects.get(id=user.id), publisher)

    def test_update_member_where_group_changed_should_switch_permissions(self):
        # Arrange
        member = self._member(group=member_group(READ, publisher=self.publisher))

        # Act
        new_group = admin_group(UPDATE_MEMBERS, publisher=self.publisher)
        self.service.update_member(member, fields={"group_id": new_group.id, "name": "Jane"})

        # Assert
        member.refresh_from_db()
        member.user.refresh_from_db()
        self.assertEqual(new_group.id, member.group_id)
        self.assertEqual("Jane", member.user.name)
        perms = self._perms(member.user, self.publisher)
        self.assertIn(UPDATE_MEMBERS.value, perms)
        self.assertNotIn(READ.value, perms)

    def test_update_member_where_group_is_itqan_internal_should_reject(self):
        # Arrange
        member = self._member(group=member_group(publisher=self.publisher))

        # Act
        with self.assertRaises(ItqanError) as ctx:
            self.service.update_member(member, fields={"group_id": itqan_internal_group().id})

        # Assert
        self.assertEqual("invalid_group", ctx.exception.error_name)
        member.refresh_from_db()
        self.assertEqual(member_group(publisher=self.publisher).id, member.group_id)

    def test_update_member_where_member_pending_should_grant_nothing(self):
        # Arrange
        member = self._member(group=member_group(publisher=self.publisher), status=PublisherMember.StatusChoice.PENDING)

        # Act
        self.service.update_member(
            member, fields={"group_id": admin_group(UPDATE_MEMBERS, publisher=self.publisher).id}
        )

        # Assert: the group is recorded, but nothing is granted before acceptance.
        member.refresh_from_db()
        self.assertEqual(admin_group(publisher=self.publisher).id, member.group_id)
        self.assertEqual(frozenset(), self._perms(member.user, self.publisher))

    def test_update_member_should_not_touch_user_groups(self):
        # Arrange
        member = self._member(group=member_group(publisher=self.publisher))

        # Act
        self.service.update_member(member, fields={"group_id": admin_group(publisher=self.publisher).id})

        # Assert: the membership, not user.groups, carries the role.
        self.assertEqual(0, member.user.groups.count())

    def test_update_member_where_user_active_elsewhere_should_keep_other_publishers_permissions(self):
        # Arrange: one user, two publishers.
        user = baker.make(User)
        other_publisher = baker.make(Publisher)
        self._member(group=member_group(READ, publisher=self.publisher), publisher=other_publisher, user=user)
        member = self._member(group=member_group(READ, publisher=self.publisher), user=user)

        # Act: change only this membership's group.
        self.service.update_member(
            member, fields={"group_id": admin_group(UPDATE_MEMBERS, publisher=self.publisher).id}
        )

        # Assert: the other publisher is unaffected, and this one's new role doesn't leak there.
        other_perms = self._perms(user, other_publisher)
        self.assertIn(READ.value, other_perms)
        self.assertNotIn(UPDATE_MEMBERS.value, other_perms)

    def test_delete_member_where_only_membership_should_remove_permissions(self):
        # Arrange
        member = self._member(group=member_group(READ, publisher=self.publisher))
        user = member.user

        # Act
        self.service.delete_member(member)

        # Assert
        self.assertEqual(frozenset(), self._perms(user, self.publisher))

    def test_delete_member_where_user_active_elsewhere_should_keep_other_permissions(self):
        # Arrange: same user and group across two publishers.
        user = baker.make(User)
        other_publisher = baker.make(Publisher)
        self._member(group=member_group(READ, publisher=self.publisher), publisher=other_publisher, user=user)
        target = self._member(group=member_group(READ, publisher=self.publisher), user=user)

        # Act
        self.service.delete_member(target)

        # Assert: removing one membership must not strip access earned by the other.
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
        self.assertIn(READ.value, self._perms(user, other_publisher))

    def test_delete_last_active_member_where_only_member_should_succeed(self):
        # Arrange
        member = self._member()

        # Act
        self.service.delete_member(member)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=member.pk).exists())

    def test_delete_active_admin_should_revoke_permissions(self):
        # Arrange
        self._member(group=admin_group(UPDATE_MEMBERS, publisher=self.publisher))
        target = self._member(group=admin_group(UPDATE_MEMBERS, publisher=self.publisher))
        user = target.user

        # Act
        self.service.delete_member(target)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
        self.assertNotIn(UPDATE_MEMBERS.value, self._perms(user, self.publisher))

    def test_delete_non_last_member_ok(self):
        # Arrange
        self._member()
        target = self._member()

        # Act
        self.service.delete_member(target)

        # Assert
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
