import uuid

from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember
from apps.publishers.services.effective_permissions import (
    effective_permissions,
    effective_permissions_by_publisher,
)
from apps.users.models import User
from apps.users.services.group import ITQAN_INTERNAL_GROUP

INVITE = PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS
READ = PermissionChoice.PORTAL_READ_RECITER


def role(publisher: Publisher, *permissions: PermissionChoice) -> Group:
    group = Group.objects.create(name=f"publisher:{publisher.id}:{uuid.uuid4().hex}")
    PublisherGroup.objects.create(group=group, publisher=publisher, name="Role")
    group.permissions.set(Permission.objects.filter(codename__in=[p.value for p in permissions]))
    return group


def join(user: User, publisher: Publisher, group: Group, status=PublisherMember.StatusChoice.ACTIVE) -> PublisherMember:
    return PublisherMember.objects.create(user=user, publisher=publisher, group=group, status=status)


class EffectivePermissionsTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher_a = baker.make(Publisher)
        self.publisher_b = baker.make(Publisher)
        self.user = baker.make(User, email="member@example.com")

    def test_member_gets_only_their_group_at_that_publisher(self):
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))
        join(self.user, self.publisher_b, role(self.publisher_b, READ))

        self.assertIn(INVITE.value, effective_permissions(self.user, self.publisher_a))
        self.assertNotIn(INVITE.value, effective_permissions(self.user, self.publisher_b))
        self.assertIn(READ.value, effective_permissions(self.user, self.publisher_b.id))

    def test_no_publisher_gives_global_plus_portal_access_only(self):
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))

        self.assertEqual(frozenset({PermissionChoice.PORTAL_ACCESS.value}), effective_permissions(self.user, None))

    def test_pending_membership_grants_nothing(self):
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE), status=PublisherMember.StatusChoice.PENDING)

        self.assertEqual(frozenset(), effective_permissions(self.user, self.publisher_a))
        self.assertEqual(frozenset(), effective_permissions(self.user, None))

    def test_publisher_role_in_user_groups_is_not_global(self):
        group = role(self.publisher_a, INVITE)
        self.user.groups.add(group)

        self.assertNotIn(INVITE.value, effective_permissions(self.user, self.publisher_b))

    def test_itqan_internal_applies_at_every_publisher(self):
        internal, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
        internal.permissions.set(Permission.objects.filter(codename__in=PermissionChoice.values))
        self.user.groups.add(internal)

        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(self.user, self.publisher_a))
        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(self.user, None))

    def test_superuser_has_everything(self):
        superuser = baker.make(User, email="root@example.com", is_superuser=True)

        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(superuser, self.publisher_a))

    def test_by_publisher_query_count_is_constant(self):
        def count_queries(n: int) -> int:
            user = baker.make(User)
            publishers = baker.make(Publisher, _quantity=n)
            for publisher in publishers:
                join(user, publisher, role(publisher, READ))
            user = User.objects.get(id=user.id)
            with CaptureQueriesContext(connection) as ctx:
                result = effective_permissions_by_publisher(user, [p.id for p in publishers])
            self.assertEqual({p.id for p in publishers}, set(result))
            return len(ctx.captured_queries)

        self.assertEqual(count_queries(1), count_queries(5))

    def test_check_permission_accepts_permission_choice_members(self):
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))

        self.assertTrue(check_permission(self.user, INVITE, publisher=self.publisher_a))
        self.assertFalse(check_permission(self.user, INVITE, publisher=self.publisher_b))


class PermissionClassTenantTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher_a = baker.make(Publisher)
        self.publisher_b = baker.make(Publisher)
        self.user = baker.make(User, email="admin-at-a@example.com")
        admin_role = role(
            self.publisher_a, PermissionChoice.PORTAL_ACCESS, PermissionChoice.PORTAL_DELETE_PUBLISHER_MEMBERS
        )
        reader_role = role(self.publisher_b, PermissionChoice.PORTAL_ACCESS)
        join(self.user, self.publisher_a, admin_role)
        join(self.user, self.publisher_b, reader_role)
        # Mirror the legacy state where membership groups were synced into user.groups.
        self.user.groups.add(admin_role, reader_role)
        self.target_a = join(baker.make(User, email="ta@example.com"), self.publisher_a, reader_role)
        self.target_b = join(baker.make(User, email="tb@example.com"), self.publisher_b, reader_role)

    def test_permission_class_denies_without_tenant(self):
        self.authenticate_user(self.user)

        resp = self.client.delete(f"/portal/members/{self.target_b.id}/")

        self.assertEqual(403, resp.status_code, resp.content)
        self.assertTrue(PublisherMember.objects.filter(id=self.target_b.id).exists())

    def test_permission_class_denies_at_tenant_where_role_lacks_it(self):
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher_b.id))

        resp = self.client.delete(f"/portal/members/{self.target_b.id}/")

        self.assertEqual(403, resp.status_code, resp.content)

    def test_permission_class_grants_from_membership_at_tenant(self):
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher_a.id))

        resp = self.client.delete(f"/portal/members/{self.target_a.id}/")

        self.assertEqual(204, resp.status_code, resp.content)
