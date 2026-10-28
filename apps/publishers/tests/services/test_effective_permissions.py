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

    def test_effective_permissions_where_member_of_two_publishers_should_scope_each_role(self):
        # Arrange
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))
        join(self.user, self.publisher_b, role(self.publisher_b, READ))

        # Act & Assert
        self.assertIn(INVITE.value, effective_permissions(self.user, self.publisher_a))
        self.assertNotIn(INVITE.value, effective_permissions(self.user, self.publisher_b))
        self.assertIn(READ.value, effective_permissions(self.user, self.publisher_b.id))

    def test_effective_permissions_where_no_publisher_should_return_global_plus_portal_access(self):
        # Arrange
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))

        # Act & Assert
        self.assertEqual(frozenset({PermissionChoice.PORTAL_ACCESS.value}), effective_permissions(self.user, None))

    def test_effective_permissions_where_membership_pending_should_grant_nothing(self):
        # Arrange
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE), status=PublisherMember.StatusChoice.PENDING)

        # Act & Assert
        self.assertEqual(frozenset(), effective_permissions(self.user, self.publisher_a))
        self.assertEqual(frozenset(), effective_permissions(self.user, None))

    def test_effective_permissions_where_role_in_user_groups_should_not_count_as_global(self):
        # Arrange
        group = role(self.publisher_a, INVITE)
        self.user.groups.add(group)

        # Act & Assert
        self.assertNotIn(INVITE.value, effective_permissions(self.user, self.publisher_b))

    def test_effective_permissions_where_itqan_internal_should_apply_at_every_publisher(self):
        # Arrange
        internal, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
        internal.permissions.set(Permission.objects.filter(codename__in=PermissionChoice.values))
        self.user.groups.add(internal)

        # Act & Assert
        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(self.user, self.publisher_a))
        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(self.user, None))

    def test_effective_permissions_where_superuser_should_return_every_permission(self):
        # Arrange
        superuser = baker.make(User, email="root@example.com", is_superuser=True)

        # Act & Assert
        self.assertEqual(frozenset(PermissionChoice.values), effective_permissions(superuser, self.publisher_a))

    def test_effective_permissions_by_publisher_where_more_memberships_should_keep_query_count(self):
        # Arrange
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

        # Act & Assert
        self.assertEqual(count_queries(1), count_queries(5))

    def test_check_permission_where_permission_choice_given_should_scope_to_publisher(self):
        # Arrange
        join(self.user, self.publisher_a, role(self.publisher_a, INVITE))

        # Act & Assert
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

    def test_permission_class_where_no_tenant_should_deny_role_permission(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        resp = self.client.delete(f"/portal/members/{self.target_b.id}/")

        # Assert
        self.assertEqual(403, resp.status_code, resp.content)
        self.assertTrue(PublisherMember.objects.filter(id=self.target_b.id).exists())

    def test_permission_class_where_tenant_role_lacks_permission_should_deny(self):
        # Arrange
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher_b.id))

        # Act
        resp = self.client.delete(f"/portal/members/{self.target_b.id}/")

        # Assert
        self.assertEqual(403, resp.status_code, resp.content)

    def test_permission_class_where_tenant_role_has_permission_should_allow(self):
        # Arrange
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher_a.id))

        # Act
        resp = self.client.delete(f"/portal/members/{self.target_a.id}/")

        # Assert
        self.assertEqual(204, resp.status_code, resp.content)
