from model_bakery import baker
from rest_framework.exceptions import PermissionDenied

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.services.membership import enforce_member_scope, enforce_publisher_membership
from apps.users.models import User


class MemberScopingTest(BaseTestCase):
    def test_pending_membership_does_not_grant_publisher_access(self):
        user = baker.make(User, is_staff=False)
        publisher = baker.make(Publisher)
        PublisherMember.objects.create(
            user=user,
            publisher=publisher,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.PENDING,
        )
        with self.assertRaises(PermissionDenied):
            enforce_publisher_membership(user, publisher.id)

    def test_active_membership_grants_access(self):
        user = baker.make(User, is_staff=False)
        publisher = baker.make(Publisher)
        PublisherMember.objects.create(
            user=user,
            publisher=publisher,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        enforce_publisher_membership(user, publisher.id)  # no raise

    def test_enforce_member_scope_blocks_cross_publisher_admin(self):
        admin = baker.make(User, is_staff=False)
        p1 = baker.make(Publisher)
        p2 = baker.make(Publisher)
        PublisherMember.objects.create(
            user=admin,
            publisher=p1,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        other = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        with self.assertRaises(PermissionDenied):
            enforce_member_scope(admin, other)

    def test_enforce_member_scope_allows_member_of_target_publisher(self):
        actor = baker.make(User, is_staff=False)
        p1 = baker.make(Publisher)
        p2 = baker.make(Publisher)
        PublisherMember.objects.create(
            user=actor,
            publisher=p1,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        PublisherMember.objects.create(
            user=actor,
            publisher=p2,
            role=PublisherMember.RoleChoice.ADMIN,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        target = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        enforce_member_scope(actor, target)  # no raise

    def test_enforce_member_scope_allows_itqan(self):
        itqan = baker.make(User, is_staff=True)
        p2 = baker.make(Publisher)
        other = PublisherMember.objects.create(
            user=baker.make(User),
            publisher=p2,
            role=PublisherMember.RoleChoice.STAFF,
            status=PublisherMember.StatusChoice.ACTIVE,
        )
        enforce_member_scope(itqan, other)  # no raise
