from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.group_helpers import member_group
from apps.users.models import User


class AdminSmokeTest(BaseTestCase):
    def test_member_and_user_admin_pages_where_group_field_used_should_render(self):
        # Arrange
        superuser = baker.make(User, is_staff=True, is_superuser=True, is_active=True)
        member = PublisherMember.objects.create(
            user=baker.make(User), publisher=baker.make(Publisher), group=member_group()
        )
        self.client.force_login(superuser)

        # Act / Assert: changelist + change form for members, and the user page with its inline.
        for url in (
            "/django-admin/publishers/publishermember/",
            f"/django-admin/publishers/publishermember/{member.id}/change/",
            f"/django-admin/users/user/{member.user_id}/change/",
        ):
            resp = self.client.get(url)
            self.assertEqual(200, resp.status_code, f"{url} -> {resp.status_code}")
