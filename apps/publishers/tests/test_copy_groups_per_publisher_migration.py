import importlib

from django.apps import apps as global_apps
from django.contrib.auth.models import Group, Permission
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember
from apps.users.models import User
from apps.users.services.group import ITQAN_INTERNAL_GROUP

migration = importlib.import_module("apps.publishers.migrations.0004_copy_groups_per_publisher")

ADMIN_PERMS = {PermissionChoice.PORTAL_ACCESS.value, PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS.value}


def _run() -> None:
    migration.copy_groups_per_publisher(global_apps, None)


class CopyGroupsPerPublisherMigrationTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher_a = baker.make(Publisher)
        self.publisher_b = baker.make(Publisher)
        self.shared = Group.objects.create(name="Admin")
        self.shared.permissions.set(Permission.objects.filter(codename__in=ADMIN_PERMS))
        self.user_a = baker.make(User, email="a@example.com")
        self.user_b = baker.make(User, email="b@example.com")
        self.member_a = baker.make(PublisherMember, publisher=self.publisher_a, user=self.user_a, group=self.shared)
        self.member_b = baker.make(
            PublisherMember,
            publisher=self.publisher_b,
            user=self.user_b,
            group=self.shared,
            status=PublisherMember.StatusChoice.PENDING,
        )
        self.user_a.groups.add(self.shared)

    def test_copy_groups_per_publisher_where_group_shared_should_copy_per_publisher(self):
        # Arrange
        _run()

        # Act & Assert
        self.member_a.refresh_from_db()
        self.member_b.refresh_from_db()
        copy_a = PublisherGroup.objects.get(publisher=self.publisher_a, name="Admin")
        copy_b = PublisherGroup.objects.get(publisher=self.publisher_b, name="Admin")
        self.assertNotEqual(copy_a.group_id, copy_b.group_id)
        self.assertEqual(copy_a.group_id, self.member_a.group_id)
        self.assertEqual(copy_b.group_id, self.member_b.group_id)
        for copy in (copy_a, copy_b):
            self.assertEqual(ADMIN_PERMS, set(copy.group.permissions.values_list("codename", flat=True)))
            self.assertTrue(copy.group.name.startswith(f"publisher:{copy.publisher_id}:"))

    def test_copy_groups_per_publisher_where_group_shared_should_leave_original_untouched(self):
        # Arrange
        _run()

        # Act & Assert
        self.shared.refresh_from_db()
        self.assertEqual("Admin", self.shared.name)
        self.assertEqual(ADMIN_PERMS, set(self.shared.permissions.values_list("codename", flat=True)))
        self.assertFalse(PublisherGroup.objects.filter(group=self.shared).exists())

    def test_copy_groups_per_publisher_where_user_in_role_and_internal_should_keep_only_internal(self):
        # Arrange
        internal, _ = Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
        self.user_a.groups.add(internal)

        # Act
        _run()

        # Assert
        self.assertEqual([ITQAN_INTERNAL_GROUP], list(self.user_a.groups.values_list("name", flat=True)))

    def test_copy_groups_per_publisher_where_run_twice_should_not_duplicate(self):
        # Arrange
        _run()
        group_count = Group.objects.count()

        # Act
        _run()

        # Assert
        self.assertEqual(group_count, Group.objects.count())
        self.assertEqual(2, PublisherGroup.objects.count())
