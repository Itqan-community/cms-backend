from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember
from apps.users.models import User


class PublisherGroupModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher_a = baker.make(Publisher)
        self.publisher_b = baker.make(Publisher)

    def _publisher_group(self, publisher: Publisher, name: str) -> PublisherGroup:
        group = Group.objects.create(name=f"publisher:{publisher.id}:{name}")
        return PublisherGroup.objects.create(group=group, publisher=publisher, name=name)

    def test_publisher_group_where_same_name_in_two_publishers_should_save(self):
        # Arrange
        self._publisher_group(self.publisher_a, "Editors")
        self._publisher_group(self.publisher_b, "Editors")

        # Act & Assert
        self.assertEqual(2, PublisherGroup.objects.filter(name="Editors").count())

    def test_publisher_group_where_duplicate_name_in_one_publisher_should_raise(self):
        # Arrange
        self._publisher_group(self.publisher_a, "Editors")
        group = Group.objects.create(name="another-opaque-name")

        # Act & Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            PublisherGroup.objects.create(group=group, publisher=self.publisher_a, name="Editors")

    def test_delete_where_publisher_group_deleted_should_delete_auth_group(self):
        # Arrange
        publisher_group = self._publisher_group(self.publisher_a, "Editors")
        group_id = publisher_group.group_id

        # Act
        publisher_group.delete()

        # Assert
        self.assertFalse(Group.objects.filter(id=group_id).exists())

    def test_delete_where_publisher_deleted_should_delete_its_auth_groups(self):
        # Arrange
        group = self._publisher_group(self.publisher_a, "Editors").group
        baker.make(
            PublisherMember, publisher=self.publisher_a, user=baker.make(User, email="m@example.com"), group=group
        )
        group_id = group.id

        # Act
        self.publisher_a.delete()

        # Assert
        self.assertFalse(Group.objects.filter(id=group_id).exists())

    def test_group_display_name_where_publisher_group_exists_should_use_its_name(self):
        # Arrange
        user = baker.make(User, email="editor@example.com")
        member = baker.make(
            PublisherMember,
            publisher=self.publisher_a,
            user=user,
            group=self._publisher_group(self.publisher_a, "Editors").group,
        )

        # Act & Assert
        self.assertEqual("Editors", member.group_display_name)

    def test_group_display_name_where_global_group_should_use_group_name(self):
        # Arrange
        user = baker.make(User, email="legacy@example.com")
        member = baker.make(
            PublisherMember, publisher=self.publisher_a, user=user, group=Group.objects.create(name="Legacy")
        )

        # Act & Assert
        self.assertEqual("Legacy", member.group_display_name)
