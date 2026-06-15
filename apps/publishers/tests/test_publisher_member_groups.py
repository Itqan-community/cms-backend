from django.contrib.auth.models import Group

from apps.core.tests.base import BaseTestCase


class MemberGroupsSeedTest(BaseTestCase):
    def test_publisher_member_admin_group_exists_with_the_four_member_perms(self):
        admin_group = Group.objects.get(name="Publisher Member Admin")
        admin_perms = set(admin_group.permissions.values_list("codename", flat=True))
        self.assertIn("portal_view_publisher_members", admin_perms)
        self.assertIn("portal_invite_publisher_members", admin_perms)
        self.assertIn("portal_update_publisher_members", admin_perms)
        self.assertIn("portal_delete_publisher_members", admin_perms)

    def test_no_publisher_staff_or_itqan_member_group_is_seeded(self):
        self.assertFalse(Group.objects.filter(name="Publisher Admin").exists())
        self.assertFalse(Group.objects.filter(name="Publisher Staff").exists())
        self.assertFalse(Group.objects.filter(name="Itqan").exists())
