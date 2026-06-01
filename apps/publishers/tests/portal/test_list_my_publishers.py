from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class ListMyPublishersTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/me/"

    def test_list_my_publishers_where_member_of_one_publisher_should_return_it(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        publisher = baker.make(Publisher, name="Tafsir Center", slug="tafsir-center")
        baker.make(PublisherMember, user=self.user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)

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
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Aaa Publisher", slug="aaa-publisher")
        pub_b = baker.make(Publisher, name="Bbb Publisher", slug="bbb-publisher")
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_b, role=PublisherMember.RoleChoice.MANAGER)

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
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        baker.make(Publisher, slug="other-publisher")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_list_my_publishers_where_results_are_ordered_by_name(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_z = baker.make(Publisher, name="Zzz Publisher", slug="zzz-publisher")
        pub_a = baker.make(Publisher, name="Aaa Publisher", slug="aaa-publisher")
        baker.make(PublisherMember, user=self.user, publisher=pub_z, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)

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
        self.give_permission(staff, PermissionChoice.PORTAL_READ_PUBLISHER)
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
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        publisher = baker.make(Publisher, name="Schema Test Pub", slug="schema-test-pub")
        baker.make(PublisherMember, user=self.user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        pub = response.json()[0]
        for field in ("id", "name", "slug", "icon_url"):
            self.assertIn(field, pub)
        self.assertNotIn("domains", pub)
