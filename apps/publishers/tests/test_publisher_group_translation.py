import importlib

from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import translation
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember
from apps.users.models import User

backfill = importlib.import_module("apps.publishers.migrations.0005_publishergroup_name_translations")


class PublisherGroupTranslationTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.publisher = baker.make(Publisher)

    def _role(self, name_en: str, name_ar: str, publisher: Publisher | None = None) -> PublisherGroup:
        group = Group.objects.create(name=f"opaque-{name_en}-{name_ar}-{publisher.id if publisher else 0}")
        return PublisherGroup.objects.create(
            group=group, publisher=publisher or self.publisher, name_en=name_en, name_ar=name_ar
        )

    def test_name_where_language_active_should_return_that_languages_name(self):
        # Arrange
        role = self._role("Editors", "المحررون")

        # Act
        with translation.override("ar"):
            arabic = PublisherGroup.objects.get(pk=role.pk).name
        with translation.override("en"):
            english = PublisherGroup.objects.get(pk=role.pk).name

        # Assert
        self.assertEqual("المحررون", arabic)
        self.assertEqual("Editors", english)

    def test_publisher_group_where_duplicate_arabic_name_in_publisher_should_raise(self):
        # Arrange
        self._role("Editors", "المحررون")

        # Act & Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._role("Writers", "المحررون")

    def test_publisher_group_where_same_names_in_two_publishers_should_save(self):
        # Arrange
        other = baker.make(Publisher)

        # Act
        self._role("Editors", "المحررون")
        self._role("Editors", "المحررون", publisher=other)

        # Assert
        self.assertEqual(2, PublisherGroup.objects.filter(name_en="Editors").count())

    def test_group_display_name_where_arabic_active_should_return_arabic_name(self):
        # Arrange
        role = self._role("Editors", "المحررون")
        member = baker.make(PublisherMember, publisher=self.publisher, user=baker.make(User), group=role.group)

        # Act
        with translation.override("ar"):
            name = PublisherMember.objects.get(pk=member.pk).group_display_name

        # Assert
        self.assertEqual("المحررون", name)

    def test_backfill_where_translations_missing_should_copy_name_to_both_languages(self):
        # Arrange: the migration runs on historical models, which modeltranslation doesn't patch.
        state_apps = (
            MigrationExecutor(connection)
            .loader.project_state(("publishers", "0005_publishergroup_name_translations"))
            .apps
        )
        role = self._role("Editors", "المحررون")
        HistoricalPublisherGroup = state_apps.get_model("publishers", "PublisherGroup")
        HistoricalPublisherGroup.objects.filter(pk=role.pk).update(name="Legacy", name_en=None, name_ar=None)

        # Act
        backfill.backfill_name_translations(state_apps, None)

        # Assert
        row = HistoricalPublisherGroup.objects.get(pk=role.pk)
        self.assertEqual(("Legacy", "Legacy"), (row.name_en, row.name_ar))
