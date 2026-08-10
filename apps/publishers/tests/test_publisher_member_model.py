from django.db import IntegrityError
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherMember
from apps.publishers.tests.group_helpers import admin_group, member_group
from apps.users.models import User


class PublisherMemberModelTest(BaseTestCase):
    def test_member_where_group_missing_should_raise(self):
        # Arrange
        user = baker.make(User)
        publisher = baker.make(Publisher)

        # Act / Assert: group is required; there is no implicit default role anymore.
        with self.assertRaises(IntegrityError):
            PublisherMember.objects.create(user=user, publisher=publisher, group=None)

    def test_status_defaults_to_pending(self):
        member = baker.make(PublisherMember, group=member_group())
        self.assertEqual(PublisherMember.StatusChoice.PENDING, member.status)

    def test_user_can_belong_to_multiple_publishers(self):
        user = baker.make(User)
        p1 = baker.make(Publisher)
        p2 = baker.make(Publisher)
        PublisherMember.objects.create(user=user, publisher=p1, group=admin_group())
        PublisherMember.objects.create(user=user, publisher=p2, group=member_group())
        self.assertEqual(2, PublisherMember.objects.filter(user=user).count())

    def test_same_user_same_publisher_is_rejected(self):
        user = baker.make(User)
        p1 = baker.make(Publisher)
        PublisherMember.objects.create(user=user, publisher=p1, group=member_group())
        with self.assertRaises(IntegrityError):
            PublisherMember.objects.create(user=user, publisher=p1, group=admin_group())
