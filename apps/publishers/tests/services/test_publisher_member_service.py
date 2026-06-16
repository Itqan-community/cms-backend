from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.services.publisher_member_service import PublisherMemberService
from apps.users.models import User


class MemberServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.service = PublisherMemberService()
        self.publisher = baker.make(Publisher)
        Group.objects.get_or_create(name="Publisher Member Admin")

    def _member(self, role=PublisherMember.RoleChoice.STAFF, status=PublisherMember.StatusChoice.ACTIVE):
        return PublisherMember.objects.create(user=baker.make(User), publisher=self.publisher, role=role, status=status)

    def test_promote_staff_to_admin_grants_perms(self):
        member = self._member(role=PublisherMember.RoleChoice.STAFF)
        updated = self.service.update_member(member, fields={"role": PublisherMember.RoleChoice.ADMIN, "name": "Jane"})
        self.assertEqual(PublisherMember.RoleChoice.ADMIN, updated.role)
        updated.user.refresh_from_db()
        self.assertEqual("Jane", updated.user.name)
        self.assertTrue(updated.user.groups.filter(name="Publisher Member Admin").exists())
        self.assertTrue(updated.user.has_perm("portal_update_publisher_members"))
        self.assertTrue(updated.user.has_perm("portal_delete_publisher_members"))

    def test_demote_admin_to_staff_revokes_admin_group_keeps_baseline(self):
        member = self._member(role=PublisherMember.RoleChoice.ADMIN)
        self.service.grant_member_perms(member)
        updated = self.service.update_member(member, fields={"role": PublisherMember.RoleChoice.STAFF})
        self.assertEqual(PublisherMember.RoleChoice.STAFF, updated.role)
        updated.user.refresh_from_db()
        self.assertFalse(updated.user.groups.filter(name="Publisher Member Admin").exists())
        # Demotion strips member-management only; the READ baseline stays.
        self.assertTrue(updated.user.groups.filter(name="Publisher Member").exists())

    def test_grant_staff_gets_baseline_not_admin_group(self):
        member = self._member(role=PublisherMember.RoleChoice.STAFF)
        self.service.grant_member_perms(member)
        member.user.refresh_from_db()
        self.assertTrue(member.user.groups.filter(name="Publisher Member").exists())
        self.assertFalse(member.user.groups.filter(name="Publisher Member Admin").exists())

    def test_delete_member_removes_baseline_group(self):
        member = self._member(role=PublisherMember.RoleChoice.STAFF)
        self.service.grant_member_perms(member)
        user = member.user
        self.service.delete_member(member)
        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name="Publisher Member").exists())

    def test_delete_last_active_member_where_only_member_should_succeed(self):
        member = self._member()
        self.service.delete_member(member)
        self.assertFalse(PublisherMember.objects.filter(pk=member.pk).exists())

    def test_delete_active_admin_revokes_perms(self):
        self._member(role=PublisherMember.RoleChoice.ADMIN)
        target = self._member(role=PublisherMember.RoleChoice.ADMIN)
        self.service.grant_member_perms(target)
        user = target.user
        self.service.delete_member(target)
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name="Publisher Member Admin").exists())

    def test_delete_non_last_member_ok(self):
        self._member()
        target = self._member()
        self.service.delete_member(target)
        self.assertFalse(PublisherMember.objects.filter(pk=target.pk).exists())
