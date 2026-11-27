from django.db import connection
from django.db.models import Q
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.middlewares.publisher_middleware import get_publisher_domain, portal_publisher_q
from apps.publishers.models import Domain, Publisher, PublisherMember
from apps.publishers.tests.group_helpers import admin_group, member_group
from apps.users.models import User


class PortalPublisherQUnitTest(BaseTestCase):
    def test_returns_empty_q_for_none_user(self) -> None:
        # Arrange / Act
        q = portal_publisher_q(None)

        # Assert
        self.assertIn("pk__in", str(q))

    def test_returns_unrestricted_q_for_staff_without_publisher(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)

        # Act
        q = portal_publisher_q(staff, publisher=None)

        # Assert
        self.assertEqual(q, Q())

    def test_staff_with_publisher_scopes_to_that_publisher(self) -> None:
        # Arrange
        staff = baker.make(User, is_staff=True)
        publisher = baker.make(Publisher, slug="staff-pub")

        # Act
        q = portal_publisher_q(staff, publisher=publisher)

        # Assert
        self.assertIn(str(publisher.id), str(q))

    def test_member_with_matching_publisher_scopes_to_it(self) -> None:
        # Arrange
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="member-pub")
        baker.make(
            PublisherMember,
            user=user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        q = portal_publisher_q(user, publisher=publisher)

        # Assert
        self.assertIn(str(publisher.id), str(q))

    def test_non_member_with_publisher_returns_empty_q(self) -> None:
        # Arrange
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="non-member-pub")

        # Act
        q = portal_publisher_q(user, publisher=publisher)

        # Assert
        self.assertIn("pk__in", str(q))

    def test_member_without_publisher_returns_all_their_publishers(self) -> None:
        # Arrange
        user = baker.make(User)
        pub_a = baker.make(Publisher, slug="pub-a")
        pub_b = baker.make(Publisher, slug="pub-b")
        baker.make(
            PublisherMember,
            user=user,
            publisher=pub_a,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        baker.make(
            PublisherMember,
            user=user,
            publisher=pub_b,
            group=member_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        q = portal_publisher_q(user, publisher=None)

        # Assert
        self.assertIn(str(pub_a.id), str(q))
        self.assertIn(str(pub_b.id), str(q))

    def test_member_with_no_memberships_and_no_publisher_returns_empty_q(self) -> None:
        # Arrange
        user = baker.make(User)

        # Act
        q = portal_publisher_q(user, publisher=None)

        # Assert
        self.assertIn("pk__in", str(q))

    def test_publisher_ids_cached_on_user_instance(self) -> None:
        # Arrange
        user = baker.make(User)
        publisher = baker.make(Publisher, slug="cached-pub")
        baker.make(
            PublisherMember,
            user=user,
            publisher=publisher,
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

        # Act
        portal_publisher_q(user, publisher=None)

        # Assert
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
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
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
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )
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
            group=admin_group(),
            status=PublisherMember.StatusChoice.ACTIVE,
        )

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


class PublisherDomainLookupCacheTest(BaseTestCase):
    def _request(self, origin: str):
        return RequestFactory().get("/reciters/", HTTP_ORIGIN=origin)

    def test_get_publisher_domain_where_host_matches_no_domain_should_query_only_once(self) -> None:
        # Arrange
        get_publisher_domain(self._request("https://no-tenant-once.example"), "Origin")

        # Act
        with CaptureQueriesContext(connection) as queries:
            result = get_publisher_domain(self._request("https://no-tenant-once.example"), "Origin")

        # Assert
        self.assertIsNone(result)
        self.assertEqual(0, len(queries))

    def test_get_publisher_domain_where_domain_is_added_after_a_miss_should_resolve_it(self) -> None:
        # Arrange
        self.assertIsNone(get_publisher_domain(self._request("https://late-tenant.example"), "Origin"))
        publisher = baker.make(Publisher)
        domain = Domain.objects.create(domain="late-tenant.example", publisher=publisher, is_active=True)

        # Act
        result = get_publisher_domain(self._request("https://late-tenant.example"), "Origin")

        # Assert
        self.assertEqual(domain.pk, result.pk)

    def test_get_publisher_domain_where_domain_is_deleted_should_stop_resolving_it(self) -> None:
        # Arrange
        domain = Domain.objects.create(domain="gone-tenant.example", publisher=baker.make(Publisher), is_active=True)
        self.assertEqual(domain.pk, get_publisher_domain(self._request("https://gone-tenant.example"), "Origin").pk)
        domain.delete()

        # Act
        result = get_publisher_domain(self._request("https://gone-tenant.example"), "Origin")

        # Assert
        self.assertIsNone(result)

    def test_get_publisher_domain_where_host_matches_should_return_cached_domain_without_query(self) -> None:
        # Arrange
        domain = Domain.objects.create(domain="hit-tenant.example", publisher=baker.make(Publisher), is_active=True)
        get_publisher_domain(self._request("https://hit-tenant.example"), "Origin")

        # Act
        with CaptureQueriesContext(connection) as queries:
            result = get_publisher_domain(self._request("https://hit-tenant.example"), "Origin")

        # Assert
        self.assertEqual(domain.pk, result.pk)
        self.assertEqual(0, len(queries))


class PublisherClosedResponseTest(BaseTestCase):
    def test_tenant_request_where_domain_is_inactive_should_return_423_in_standard_envelope(self) -> None:
        # Arrange
        publisher = baker.make(Publisher, slug="closed-pub")
        baker.make(Domain, publisher=publisher, domain="closed.example.com", is_active=False)

        # Act
        response = self.client.get("/tenant/reciters/", headers={"X-Tenant": "closed.example.com"})

        # Assert
        self.assertEqual(423, response.status_code, response.content)
        body = response.json()
        self.assertEqual("publisher_closed", body["error_name"])
        self.assertTrue(body["message"])
        self.assertIsNone(body["extra"])
