from django.contrib.auth.models import Group, Permission
from django.core.management.sql import emit_post_migrate_signal

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.services.group import ITQAN_INTERNAL_GROUP


def _run_post_migrate() -> None:
    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")


class PostMigrateGroupSeedTest(BaseTestCase):
    def test_post_migrate_where_publisher_group_edited_should_keep_its_permissions(self):
        # Arrange
        group, _ = Group.objects.get_or_create(name="Publisher Member Admin")
        edited = Permission.objects.get(codename=PermissionChoice.PORTAL_CREATE_RECITATION.value)
        group.permissions.set([edited])

        # Act
        _run_post_migrate()

        # Assert
        self.assertEqual(["portal_create_recitation"], list(group.permissions.values_list("codename", flat=True)))

    def test_post_migrate_where_publisher_groups_missing_should_not_create_them(self):
        # Arrange
        Group.objects.filter(name__in=["Publisher Member", "Publisher Member Admin"]).delete()

        # Act
        _run_post_migrate()

        # Assert
        self.assertFalse(Group.objects.filter(name__in=["Publisher Member", "Publisher Member Admin"]).exists())

    def test_post_migrate_where_run_should_grant_itqan_internal_every_permission(self):
        # Arrange
        _run_post_migrate()

        # Act & Assert
        perms = set(Group.objects.get(name=ITQAN_INTERNAL_GROUP).permissions.values_list("codename", flat=True))
        self.assertEqual(set(PermissionChoice.values), perms)  # type: ignore[attr-defined]
