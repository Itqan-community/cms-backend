"""Rollout of the per-category content-editing permissions.

Editing an asset's text used to need only PORTAL_UPDATE_*; it now needs
PORTAL_EDIT_*_CONTENT. The migration has already run when tests execute, so its
functions are exercised directly against groups and users created here.
"""

import importlib

from django.apps import apps as global_apps
from django.contrib.auth.models import Group, Permission

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User

# The module name starts with a digit, so it cannot be imported with `import`.
_migration = importlib.import_module("apps.publishers.migrations.0016_grant_edit_content_to_editors")


class GrantEditContentMigrationTest(BaseTestCase):
    def _permission(self, choice: PermissionChoice) -> Permission:
        return Permission.objects.get(codename=choice.value)

    def _group_with(self, name: str, *choices: PermissionChoice) -> Group:
        group = Group.objects.create(name=name)
        group.permissions.add(*[self._permission(choice) for choice in choices])
        return group

    def _codenames(self, group: Group) -> set[str]:
        return set(group.permissions.values_list("codename", flat=True))

    def test_grant_edit_content_where_group_updates_translations_should_grant_translation_content_only(self):
        # Arrange
        group = self._group_with("Translators", PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act
        _migration.grant_edit_content(global_apps, None)

        # Assert — today's editors keep editing text after deploy, and only for their category
        codenames = self._codenames(group)
        self.assertIn(PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT.value, codenames)
        self.assertNotIn(PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT.value, codenames)

    def test_grant_edit_content_where_group_updates_tafsirs_should_grant_tafsir_content(self):
        # Arrange
        group = self._group_with("Tafsir Editors", PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        _migration.grant_edit_content(global_apps, None)

        # Assert
        self.assertIn(PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT.value, self._codenames(group))

    def test_grant_edit_content_where_group_only_reviews_should_grant_nothing(self):
        # Arrange
        group = self._group_with("Reviewers", PermissionChoice.PORTAL_REVIEW_CONTENT)

        # Act
        _migration.grant_edit_content(global_apps, None)

        # Assert
        self.assertEqual(self._codenames(group), {PermissionChoice.PORTAL_REVIEW_CONTENT.value})

    def test_grant_edit_content_where_user_holds_update_directly_should_grant_it_to_the_user(self):
        # Arrange
        user = User.objects.create_user(email="direct-editor@example.com", name="Direct", is_staff=True)
        user.user_permissions.add(self._permission(PermissionChoice.PORTAL_UPDATE_TAFSIR))

        # Act
        _migration.grant_edit_content(global_apps, None)

        # Assert
        self.assertTrue(
            user.user_permissions.filter(codename=PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT.value).exists()
        )

    def test_revoke_edit_content_where_reversed_should_remove_it_from_updating_groups(self):
        # Arrange
        group = self._group_with("Translators", PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        _migration.grant_edit_content(global_apps, None)

        # Act
        _migration.revoke_edit_content(global_apps, None)

        # Assert
        self.assertNotIn(PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT.value, self._codenames(group))
