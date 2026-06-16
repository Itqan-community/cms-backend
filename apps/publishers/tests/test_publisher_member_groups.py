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

    def test_publisher_member_baseline_group_exists_with_read_perms(self):
        base_group = Group.objects.get(name="Publisher Member")
        perms = set(base_group.permissions.values_list("codename", flat=True))
        self.assertEqual(
            {
                "portal_access",
                "portal_read_reciter",
                "portal_read_recitation",
                "portal_read_tafsir",
                "portal_read_translation",
                "portal_read_publisher",
                "portal_view_publisher_members",
            },
            perms,
        )
        # Baseline must NOT grant role/group management or any write action.
        self.assertNotIn("portal_read_group", perms)
        self.assertNotIn("portal_invite_publisher_members", perms)

    def test_no_publisher_staff_or_itqan_member_group_is_seeded(self):
        self.assertFalse(Group.objects.filter(name="Publisher Admin").exists())
        self.assertFalse(Group.objects.filter(name="Publisher Staff").exists())
        self.assertFalse(Group.objects.filter(name="Itqan").exists())
