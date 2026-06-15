from django.db import IntegrityError
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.users.models import User


class PublisherMemberModelTest(BaseTestCase):
    def test_role_choices_are_admin_and_staff(self):
        self.assertEqual(PublisherMember.RoleChoice.ADMIN, "admin")
        self.assertEqual(PublisherMember.RoleChoice.STAFF, "staff")

    def test_status_defaults_to_pending(self):
        member = baker.make(PublisherMember, role=PublisherMember.RoleChoice.STAFF)
        self.assertEqual(PublisherMember.StatusChoice.PENDING, member.status)

    def test_user_can_belong_to_multiple_publishers(self):
        user = baker.make(User)
        p1 = baker.make(Publisher)
        p2 = baker.make(Publisher)
        PublisherMember.objects.create(user=user, publisher=p1, role=PublisherMember.RoleChoice.ADMIN)
        PublisherMember.objects.create(user=user, publisher=p2, role=PublisherMember.RoleChoice.STAFF)
        self.assertEqual(2, PublisherMember.objects.filter(user=user).count())

    def test_same_user_same_publisher_is_rejected(self):
        user = baker.make(User)
        p1 = baker.make(Publisher)
        PublisherMember.objects.create(user=user, publisher=p1, role=PublisherMember.RoleChoice.STAFF)
        with self.assertRaises(IntegrityError):
            PublisherMember.objects.create(user=user, publisher=p1, role=PublisherMember.RoleChoice.ADMIN)
