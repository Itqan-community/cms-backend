from django.db.models import Q
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.middlewares.publisher_middleware import portal_publisher_q
from apps.publishers.models import Domain, Publisher, PublisherMember
from apps.users.models import User


class PortalPublisherQUnitTest(BaseTestCase):
    def test_returns_empty_q_for_none_user(self) -> None:
        q = portal_publisher_q(None)
        self.assertIn("pk__in", str(q))

    def test_returns_unrestricted_q_for_staff_without_publisher(self) -> None:
        staff = baker.make(User, is_staff=True)
        q = portal_publisher_q(staff, publisher=None)
        self.assertEqual(q, Q())

    def test_staff_with_publisher_scopes_to_that_publisher(self) -> None:
        staff = baker.make(User, is_staff=True)
        publisher = baker.make(Publisher, slug="staff-pub")
        q = portal_publisher_q(staff, publisher=publisher)
        self.assertIn(str(publisher.id), str(q))

    def test_member_with_matching_publisher_scopes_to_it(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="member-pub")
        baker.make(PublisherMember, user=user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)
        q = portal_publisher_q(user, publisher=publisher)
        self.assertIn(str(publisher.id), str(q))

    def test_non_member_with_publisher_returns_empty_q(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="non-member-pub")
        q = portal_publisher_q(user, publisher=publisher)
        self.assertIn("pk__in", str(q))

    def test_member_without_publisher_returns_all_their_publishers(self) -> None:
        user = baker.make(User)
        pub_a = baker.make(Publisher, slug="pub-a")
        pub_b = baker.make(Publisher, slug="pub-b")
        baker.make(PublisherMember, user=user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=user, publisher=pub_b, role=PublisherMember.RoleChoice.MANAGER)
        q = portal_publisher_q(user, publisher=None)
        self.assertIn(str(pub_a.id), str(q))
        self.assertIn(str(pub_b.id), str(q))

    def test_member_with_no_memberships_and_no_publisher_returns_empty_q(self) -> None:
        user = baker.make(User)
        q = portal_publisher_q(user, publisher=None)
        self.assertIn("pk__in", str(q))

    def test_publisher_ids_cached_on_user_instance(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="cached-pub")
        baker.make(PublisherMember, user=user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)
        portal_publisher_q(user, publisher=None)
        self.assertTrue(hasattr(user, "_cached_publisher_ids"))
        self.assertIn(publisher.id, user._cached_publisher_ids)


class XTenantHeaderScopingTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/"

    def _set_x_tenant_id(self, user: User, publisher: Publisher) -> None:
        self.authenticate_user(user)
        self.client.credentials(**self.client._credentials, HTTP_X_TENANT=str(publisher.id))

    def _set_x_tenant_domain(self, user: User, domain: Domain) -> None:
        self.authenticate_user(user)
        self.client.credentials(**self.client._credentials, HTTP_X_TENANT=domain.domain)

    def test_x_tenant_as_publisher_id_scopes_list_to_that_publisher(self) -> None:
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha")
        pub_b = baker.make(Publisher, name="Beta", slug="beta")
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_b, role=PublisherMember.RoleChoice.OWNER)
        self._set_x_tenant_id(self.user, pub_a)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("Alpha", body["results"][0]["name"])

    def test_x_tenant_as_domain_scopes_list_to_that_publisher(self) -> None:
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha-domain")
        pub_b = baker.make(Publisher, name="Beta", slug="beta-domain")
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_b, role=PublisherMember.RoleChoice.OWNER)
        domain_a = baker.make(Domain, publisher=pub_a, domain="alpha.example.com", is_active=True)
        self._set_x_tenant_domain(self.user, domain_a)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("Alpha", body["results"][0]["name"])

    def test_x_tenant_id_for_non_member_publisher_returns_empty(self) -> None:
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        other_pub = baker.make(Publisher, name="Other", slug="other")
        self._set_x_tenant_id(self.user, other_pub)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(0, response.json()["count"])

    def test_no_x_tenant_header_returns_all_user_publishers(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha-no-header")
        pub_b = baker.make(Publisher, name="Beta", slug="beta-no-header")
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_b, role=PublisherMember.RoleChoice.OWNER)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(2, response.json()["count"])

    def test_staff_with_x_tenant_id_scopes_to_that_publisher(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        self.give_permission(staff, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha-staff")
        baker.make(Publisher, name="Beta", slug="beta-staff")
        baker.make(Publisher, name="Gamma", slug="gamma-staff")
        self._set_x_tenant_id(staff, pub_a)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("Alpha", body["results"][0]["name"])

    def test_staff_without_x_tenant_header_returns_all_publishers(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        self.authenticate_user(staff)
        self.give_permission(staff, PermissionChoice.PORTAL_READ_PUBLISHER)
        baker.make(Publisher, slug="p1")
        baker.make(Publisher, slug="p2")
        baker.make(Publisher, slug="p3")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(3, response.json()["count"])
