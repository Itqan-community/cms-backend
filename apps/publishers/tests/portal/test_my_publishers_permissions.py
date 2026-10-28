from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.group_helpers import publisher_role
from apps.users.models import User

ACCESS = PermissionChoice.PORTAL_ACCESS
INVITE = PermissionChoice.PORTAL_INVITE_PUBLISHER_MEMBERS


class MyPublishersPermissionsTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User, email="multi@example.com")
        self.publisher_a = baker.make(Publisher, name="A")
        self.publisher_b = baker.make(Publisher, name="B")

    def _join(self, publisher: Publisher, *permissions: PermissionChoice) -> None:
        PublisherMember.objects.create(
            user=self.user,
            publisher=publisher,
            group=publisher_role(publisher, "Role", ACCESS, *permissions),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_each_publisher_lists_its_own_permissions(self) -> None:
        self._join(self.publisher_a, INVITE)
        self._join(self.publisher_b)
        self.authenticate_user(self.user)

        response = self.client.get("/portal/publishers/me/")

        self.assertEqual(200, response.status_code, response.content)
        by_name = {item["name"]: item["permissions"] for item in response.json()}
        self.assertIn(INVITE.value, by_name["A"])
        self.assertNotIn(INVITE.value, by_name["B"])
        self.assertEqual(sorted(by_name["A"]), by_name["A"])

    def test_my_publishers_query_count_constant(self) -> None:
        def count() -> int:
            self.authenticate_user(self.user)
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get("/portal/publishers/me/")
            self.assertEqual(200, response.status_code, response.content)
            return len(ctx.captured_queries)

        self._join(self.publisher_a)
        count()  # warm per-process caches
        one = count()
        for publisher in baker.make(Publisher, _quantity=4):
            self._join(publisher, INVITE)

        self.assertEqual(one, count())

    def test_profile_permissions_still_union_of_memberships(self) -> None:
        self._join(self.publisher_a, INVITE)
        self._join(self.publisher_b)
        self.authenticate_user(self.user)

        response = self.client.get("/cms-api/auth/profile/")

        self.assertEqual(200, response.status_code, response.content)
        codes = {p["code_name"] for p in response.json()["permissions"]}
        self.assertIn(INVITE.value, codes)
        self.assertIn(ACCESS.value, codes)
