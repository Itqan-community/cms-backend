from django.db.models import Q
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests import BaseTestCase
from apps.publishers.middlewares.publisher_middleware import portal_publisher_q
from apps.publishers.models import Domain, Publisher, PublisherMember
from apps.users.models import User


class PortalPublisherQUnitTest(BaseTestCase):
    def _make_domain(self, publisher: Publisher) -> Domain:
        return baker.make(Domain, publisher=publisher, domain="unit.example.com")

    def test_returns_empty_q_for_none_user(self) -> None:
        q = portal_publisher_q(None)
        self.assertIn("pk__in", str(q))

    def test_returns_unrestricted_q_for_staff_without_domain(self) -> None:
        staff = baker.make(User, is_staff=True)
        q = portal_publisher_q(staff, domain=None)
        self.assertEqual(q, Q())

    def test_staff_with_domain_scopes_to_that_publisher(self) -> None:
        staff = baker.make(User, is_staff=True)
        publisher = baker.make(Publisher, slug="staff-pub")
        domain = self._make_domain(publisher)
        q = portal_publisher_q(staff, domain=domain)
        self.assertIn(str(publisher.id), str(q))

    def test_member_with_matching_domain_scopes_to_that_publisher(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="member-pub")
        baker.make(PublisherMember, user=user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)
        domain = self._make_domain(publisher)
        q = portal_publisher_q(user, domain=domain)
        self.assertIn(str(publisher.id), str(q))

    def test_non_member_with_domain_returns_empty_q(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="non-member-pub")
        domain = self._make_domain(publisher)
        # user has no membership for this publisher
        q = portal_publisher_q(user, domain=domain)
        self.assertIn("pk__in", str(q))

    def test_member_without_domain_returns_all_their_publishers(self) -> None:
        user = baker.make(User)
        pub_a = baker.make(Publisher, slug="pub-a")
        pub_b = baker.make(Publisher, slug="pub-b")
        baker.make(PublisherMember, user=user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=user, publisher=pub_b, role=PublisherMember.RoleChoice.MANAGER)
        q = portal_publisher_q(user, domain=None)
        q_str = str(q)
        self.assertIn(str(pub_a.id), q_str)
        self.assertIn(str(pub_b.id), q_str)

    def test_member_with_no_memberships_and_no_domain_returns_empty_q(self) -> None:
        user = baker.make(User)
        q = portal_publisher_q(user, domain=None)
        self.assertIn("pk__in", str(q))

    def test_publisher_ids_cached_on_user_instance(self) -> None:
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="cached-pub")
        baker.make(PublisherMember, user=user, publisher=publisher, role=PublisherMember.RoleChoice.OWNER)
        portal_publisher_q(user, domain=None)
        self.assertTrue(hasattr(user, "_cached_publisher_ids"))
        self.assertIn(publisher.id, user._cached_publisher_ids)


class XTenantHeaderScopingTest(BaseTestCase):
    """
    Verifies that sending X-Tenant on portal requests narrows results to the
    publisher that owns that domain (when the user is a member of it).
    """

    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/publishers/"

    def _authenticate_with_tenant(self, user: User, domain: Domain) -> None:
        self.authenticate_user(user)
        self.client.credentials(
            **dict(self.client._credentials.items()),
            HTTP_X_TENANT=domain.domain,
        )

    def test_x_tenant_header_scopes_list_to_that_publisher(self) -> None:
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha")
        pub_b = baker.make(Publisher, name="Beta", slug="beta")
        baker.make(PublisherMember, user=self.user, publisher=pub_a, role=PublisherMember.RoleChoice.OWNER)
        baker.make(PublisherMember, user=self.user, publisher=pub_b, role=PublisherMember.RoleChoice.OWNER)
        domain_a = baker.make(Domain, publisher=pub_a, domain="alpha.example.com", is_active=True)
        self._authenticate_with_tenant(self.user, domain_a)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(1, body["count"])
        self.assertEqual("Alpha", body["results"][0]["name"])

    def test_x_tenant_header_for_non_member_publisher_returns_empty(self) -> None:
        # Arrange
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        other_pub = baker.make(Publisher, name="Other", slug="other")
        domain = baker.make(Domain, publisher=other_pub, domain="other.example.com", is_active=True)
        # user has no membership for other_pub
        self._authenticate_with_tenant(self.user, domain)

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

    def test_staff_with_x_tenant_header_scopes_to_that_publisher(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        self.give_permission(staff, PermissionChoice.PORTAL_READ_PUBLISHER)
        pub_a = baker.make(Publisher, name="Alpha", slug="alpha-staff")
        baker.make(Publisher, name="Beta", slug="beta-staff")
        baker.make(Publisher, name="Gamma", slug="gamma-staff")
        domain_a = baker.make(Domain, publisher=pub_a, domain="alpha-staff.example.com", is_active=True)
        self._authenticate_with_tenant(staff, domain_a)

        # Act
        response = self.client.get(self.url)

        # Assert — staff scoped to the x-tenant publisher only
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

    def test_x_tenant_inactive_domain_returns_423(self) -> None:
        # Arrange — inactive domain triggers the middleware lock response
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_PUBLISHER)
        publisher = baker.make(Publisher, slug="locked-pub")
        inactive_domain = baker.make(Domain, publisher=publisher, domain="locked.example.com", is_active=False)
        self.client.credentials(
            **dict(self.client._credentials.items()),
            HTTP_X_TENANT=inactive_domain.domain,
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(423, response.status_code, response.content)
