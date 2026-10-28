from django.contrib.auth.models import Group, Permission
from django.core.management.sql import emit_post_migrate_signal

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.services.group import ITQAN_INTERNAL_GROUP


def _run_post_migrate() -> None:
    emit_post_migrate_signal(verbosity=0, interactive=False, db="default")


class PostMigrateGroupSeedTest(BaseTestCase):
    def test_post_migrate_keeps_permissions_edited_on_a_publisher_group(self):
        group, _ = Group.objects.get_or_create(name="Publisher Member Admin")
        edited = Permission.objects.get(codename=PermissionChoice.PORTAL_CREATE_RECITATION.value)
        group.permissions.set([edited])

        _run_post_migrate()

        self.assertEqual(["portal_create_recitation"], list(group.permissions.values_list("codename", flat=True)))

    def test_post_migrate_does_not_create_publisher_groups(self):
        Group.objects.filter(name__in=["Publisher Member", "Publisher Member Admin"]).delete()

        _run_post_migrate()

        self.assertFalse(Group.objects.filter(name__in=["Publisher Member", "Publisher Member Admin"]).exists())

    def test_post_migrate_grants_every_permission_to_itqan_internal(self):
        _run_post_migrate()

        perms = set(Group.objects.get(name=ITQAN_INTERNAL_GROUP).permissions.values_list("codename", flat=True))
        self.assertEqual(set(PermissionChoice.values), perms)  # type: ignore[attr-defined]
