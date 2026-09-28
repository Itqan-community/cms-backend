"""Targeting rule of the ``PORTAL_ACCESS_ALL_LANGUAGES`` rollout migration.

The migration has already run by the time tests execute, so this exercises its
function directly against groups created here. What matters is the rule itself:
groups are chosen by the permissions they hold, not by name — the seeded groups
carry no content-edit permissions, so a name-based rule would miss real editors.
"""

import importlib

from django.apps import apps as global_apps
from django.contrib.auth.models import Group, Permission

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so it cannot be imported with `import`.
_migration = importlib.import_module("apps.publishers.migrations.0015_grant_access_all_languages_to_editor_groups")


class GrantAccessAllLanguagesMigrationTest(BaseTestCase):
    def _run_forward(self):
        _migration.grant_bypass_to_editor_groups(global_apps, None)

    def _run_backward(self):
        _migration.revoke_bypass_from_editor_groups(global_apps, None)

    def _permission(self, choice: PermissionChoice) -> Permission:
        return Permission.objects.get(codename=choice.value)

    def _group_with(self, name: str, *choices: PermissionChoice) -> Group:
        group = Group.objects.create(name=name)
        group.permissions.add(*[self._permission(choice) for choice in choices])
        return group

    def _has_bypass(self, group: Group) -> bool:
        return group.permissions.filter(codename=PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES.value).exists()

    def test_migration_where_group_edits_translations_should_grant_bypass(self):
        # Arrange
        group = self._group_with("Translators", PermissionChoice.PORTAL_UPDATE_TRANSLATION)

        # Act
        self._run_forward()

        # Assert — today's editors keep working after deploy
        self.assertTrue(self._has_bypass(group))

    def test_migration_where_group_edits_tafsirs_should_grant_bypass(self):
        # Arrange
        group = self._group_with("Tafsir Editors", PermissionChoice.PORTAL_UPDATE_TAFSIR)

        # Act
        self._run_forward()

        # Assert
        self.assertTrue(self._has_bypass(group))

    def test_migration_where_group_only_reviews_should_not_grant_bypass(self):
        # Arrange — reviewers are already gated by assignment; granting the bypass
        # would widen their access rather than preserve it.
        group = self._group_with("Reviewers", PermissionChoice.PORTAL_REVIEW_CONTENT)

        # Act
        self._run_forward()

        # Assert
        self.assertFalse(self._has_bypass(group))

    def test_migration_where_group_only_reads_should_not_grant_bypass(self):
        # Arrange
        group = self._group_with("Readers", PermissionChoice.PORTAL_READ_TRANSLATION)

        # Act
        self._run_forward()

        # Assert
        self.assertFalse(self._has_bypass(group))

    def test_migration_reverse_should_remove_bypass_from_editor_groups(self):
        # Arrange
        group = self._group_with("Translators", PermissionChoice.PORTAL_UPDATE_TRANSLATION)
        self._run_forward()

        # Act
        self._run_backward()

        # Assert
        self.assertFalse(self._has_bypass(group))
