from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Domain, Publisher, PublisherMember
from apps.publishers.tests.group_helpers import admin_group, member_group
from apps.users.models import User


class ListMyPublishersTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/me/"

    def test_list_my_publishers_where_member_of_one_publisher_should_return_it(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        publisher = baker.make(Publisher, name="Tafsir Center", slug="tafsir-center")
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, len(body))
        self.assertEqual("Tafsir Center", body[0]["name"])
        self.assertEqual("tafsir-center", body[0]["slug"])

    def test_list_my_publishers_where_member_of_multiple_publishers_should_return_all(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        pub_a = baker.make(Publisher, name="Aaa Publisher", slug="aaa-publisher")
        pub_b = baker.make(Publisher, name="Bbb Publisher", slug="bbb-publisher")
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=pub_a,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=pub_b,
            group=member_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(2, len(body))
        names = [p["name"] for p in body]
        self.assertIn("Aaa Publisher", names)
        self.assertIn("Bbb Publisher", names)

    def test_list_my_publishers_where_not_a_member_should_return_empty(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        baker.make(Publisher, slug="other-publisher")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_list_my_publishers_where_results_are_ordered_by_name(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        pub_z = baker.make(Publisher, name="Zzz Publisher", slug="zzz-publisher")
        pub_a = baker.make(Publisher, name="Aaa Publisher", slug="aaa-publisher")
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=pub_z,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=pub_a,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Aaa Publisher", body[0]["name"])
        self.assertEqual("Zzz Publisher", body[1]["name"])

    def test_list_my_publishers_where_staff_user_should_return_all_publishers(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        self.authenticate_user(staff)
        self.give_permission(staff, PermissionChoice.PORTAL_ACCESS)
        baker.make(Publisher, slug="pub-1")
        baker.make(Publisher, slug="pub-2")
        baker.make(Publisher, slug="pub-3")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(3, len(response.json()))

    def test_list_my_publishers_where_unauthenticated_should_return_401(self) -> None:
        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_list_my_publishers_where_only_portal_access_should_return_memberships(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        publisher = baker.make(Publisher, name="Tafsir Center", slug="tafsir-center")
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["tafsir-center"], [p["slug"] for p in response.json()])

    def test_list_my_publishers_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_list_my_publishers_response_schema_has_required_fields(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        publisher = baker.make(Publisher, name="Schema Test Pub", slug="schema-test-pub")
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        pub = response.json()[0]
        for field in ("id", "name", "slug", "icon_url"):
            self.assertIn(field, pub)
        self.assertNotIn("domains", pub)

    def _join(self, publisher: Publisher) -> None:
        baker.make(
            PublisherMember,
            user=self.user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

    def test_list_my_publishers_where_publisher_has_a_domain_should_return_has_website_true(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        with_site = baker.make(Publisher, name="Aaa With Site", slug="aaa-with-site")
        without_site = baker.make(Publisher, name="Bbb No Site", slug="bbb-no-site")
        self._join(with_site)
        self._join(without_site)
        baker.make(Domain, publisher=with_site, domain="with-site.example.com")
        baker.make(Domain, publisher=with_site, domain="www2.with-site.example.com")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {"aaa-with-site": True, "bbb-no-site": False},
            {p["slug"]: p["has_website"] for p in response.json()},
        )

    def test_list_my_publishers_where_only_domain_is_inactive_should_return_has_website_true(self) -> None:
        # Arrange: an inactive domain is a site closed for maintenance, not a missing site
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_ACCESS)
        publisher = baker.make(Publisher, slug="paused-site")
        self._join(publisher)
        baker.make(Domain, publisher=publisher, domain="paused.example.com", is_active=False)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()[0]["has_website"])

    def test_list_my_publishers_where_more_publishers_have_domains_should_not_add_queries(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        self.authenticate_user(staff)
        self.give_permission(staff, PermissionChoice.PORTAL_ACCESS)
        first = baker.make(Publisher, slug="pub-first")
        baker.make(Domain, publisher=first, domain="first.example.com")
        with CaptureQueriesContext(connection) as one_publisher:
            self.client.get(self.url)
        for index in range(5):
            publisher = baker.make(Publisher, slug=f"pub-more-{index}")
            baker.make(Domain, publisher=publisher, domain=f"more-{index}.example.com")

        # Act
        with CaptureQueriesContext(connection) as six_publishers:
            response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(6, len(response.json()))
        self.assertEqual(len(one_publisher.captured_queries), len(six_publishers.captured_queries))
