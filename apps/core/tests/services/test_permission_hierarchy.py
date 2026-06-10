from django.contrib.auth.models import Group

from apps.core.permissions import PermissionChoice
from apps.core.services.permissions import PermissionHierarchyService
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class PermissionHierarchyWithImpliedTests(BaseTestCase):
    def setUp(self) -> None:
        self.service = PermissionHierarchyService()

    def test_with_implied_where_create_should_imply_read(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_CREATE_RECITER]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        self.assertEqual(
            expanded,
            {PermissionChoice.PORTAL_CREATE_RECITER, PermissionChoice.PORTAL_READ_RECITER},
        )

    def test_with_implied_where_delete_should_imply_only_read(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_DELETE_RECITER]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        # DELETE implies READ only; it does not pull in CREATE or UPDATE.
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_DELETE_RECITER,
                PermissionChoice.PORTAL_READ_RECITER,
            },
        )

    def test_with_implied_where_update_should_imply_only_read(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_UPDATE_RECITER]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        # UPDATE implies READ only; it does not require CREATE.
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_UPDATE_RECITER,
                PermissionChoice.PORTAL_READ_RECITER,
            },
        )

    def test_with_implied_where_read_only_should_return_itself(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_READ_RECITER]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        self.assertEqual(expanded, {PermissionChoice.PORTAL_READ_RECITER})

    def test_with_implied_where_upload_timing_should_imply_recitation_update_chain(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_UPLOAD_TIMING]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_UPLOAD_TIMING,
                PermissionChoice.PORTAL_UPDATE_RECITATION,
                PermissionChoice.PORTAL_READ_RECITATION,
            },
        )

    def test_with_implied_where_given_raw_string_codename_should_resolve_choice(self):
        # Arrange
        permissions = ["portal_create_tafsir"]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        self.assertEqual(
            expanded,
            {PermissionChoice.PORTAL_CREATE_TAFSIR, PermissionChoice.PORTAL_READ_TAFSIR},
        )

    def test_with_implied_where_mixed_groups_should_expand_independently(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_CREATE_RECITER, PermissionChoice.PORTAL_DELETE_PUBLISHER]

        # Act
        expanded = self.service.with_implied(permissions)

        # Assert
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_CREATE_RECITER,
                PermissionChoice.PORTAL_READ_RECITER,
                PermissionChoice.PORTAL_DELETE_PUBLISHER,
                PermissionChoice.PORTAL_READ_PUBLISHER,
            },
        )


class PermissionHierarchyWithDependentsTests(BaseTestCase):
    def setUp(self) -> None:
        self.service = PermissionHierarchyService()

    def test_with_dependents_where_read_revoked_should_cascade_up_to_delete(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_READ_RECITER]

        # Act
        expanded = self.service.with_dependents(permissions)

        # Assert
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_READ_RECITER,
                PermissionChoice.PORTAL_CREATE_RECITER,
                PermissionChoice.PORTAL_UPDATE_RECITER,
                PermissionChoice.PORTAL_DELETE_RECITER,
            },
        )

    def test_with_dependents_where_delete_revoked_should_return_itself(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_DELETE_RECITER]

        # Act
        expanded = self.service.with_dependents(permissions)

        # Assert
        self.assertEqual(expanded, {PermissionChoice.PORTAL_DELETE_RECITER})

    def test_with_dependents_where_recitation_update_revoked_should_include_upload_timing(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_UPDATE_RECITATION]

        # Act
        expanded = self.service.with_dependents(permissions)

        # Assert
        # UPLOAD_TIMING depends on UPDATE, but DELETE does not, so DELETE survives.
        self.assertEqual(
            expanded,
            {
                PermissionChoice.PORTAL_UPDATE_RECITATION,
                PermissionChoice.PORTAL_UPLOAD_TIMING,
            },
        )


class PermissionHierarchyGrantTests(BaseTestCase):
    def setUp(self) -> None:
        self.service = PermissionHierarchyService()
        self.user = User.objects.create_user(email="grantee@example.com", password="x")

    def _user_perm_codenames(self) -> set[str]:
        # Re-fetch to bust the permission cache populated by has_perm/user_permissions.
        user = User.objects.get(pk=self.user.pk)
        return {perm.split(".", 1)[-1] for perm in user.get_all_permissions()}

    def test_grant_to_user_where_create_granted_should_assign_implied_read(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_CREATE_RECITER]

        # Act
        self.service.grant_to_user(self.user, permissions)

        # Assert
        codenames = self._user_perm_codenames()
        self.assertIn(PermissionChoice.PORTAL_CREATE_RECITER.value, codenames)
        self.assertIn(PermissionChoice.PORTAL_READ_RECITER.value, codenames)

    def test_grant_to_user_where_called_twice_should_be_idempotent(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_DELETE_RECITER]

        # Act
        self.service.grant_to_user(self.user, permissions)
        self.service.grant_to_user(self.user, permissions)

        # Assert
        # DELETE implies READ only, so the user holds exactly {DELETE, READ}.
        self.assertEqual(self.user.user_permissions.count(), 2)

    def test_grant_to_user_where_granted_should_return_expanded_set(self):
        # Arrange
        permissions = [PermissionChoice.PORTAL_CREATE_RECITER]

        # Act
        applied = self.service.grant_to_user(self.user, permissions)

        # Assert
        self.assertEqual(
            applied,
            {PermissionChoice.PORTAL_CREATE_RECITER, PermissionChoice.PORTAL_READ_RECITER},
        )

    def test_grant_to_group_where_update_granted_should_assign_read_only(self):
        # Arrange
        group = Group.objects.create(name="editors")
        permissions = [PermissionChoice.PORTAL_UPDATE_TRANSLATION]

        # Act
        self.service.grant_to_group(group, permissions)

        # Assert
        # UPDATE implies READ only; it does not pull in CREATE.
        codenames = {perm.codename for perm in group.permissions.all()}
        self.assertEqual(
            codenames,
            {
                PermissionChoice.PORTAL_UPDATE_TRANSLATION.value,
                PermissionChoice.PORTAL_READ_TRANSLATION.value,
            },
        )


class PermissionHierarchyRevokeTests(BaseTestCase):
    def setUp(self) -> None:
        self.service = PermissionHierarchyService()
        self.user = User.objects.create_user(email="revokee@example.com", password="x")

    def _user_perm_codenames(self) -> set[str]:
        # Re-fetch to bust the permission cache populated by has_perm/user_permissions.
        user = User.objects.get(pk=self.user.pk)
        return {perm.split(".", 1)[-1] for perm in user.get_all_permissions()}

    def test_revoke_from_user_where_read_revoked_should_remove_whole_group(self):
        # Arrange
        self.service.grant_to_user(self.user, [PermissionChoice.PORTAL_DELETE_RECITER])

        # Act
        self.service.revoke_from_user(self.user, [PermissionChoice.PORTAL_READ_RECITER])

        # Assert
        codenames = self._user_perm_codenames()
        self.assertNotIn(PermissionChoice.PORTAL_READ_RECITER.value, codenames)
        self.assertNotIn(PermissionChoice.PORTAL_CREATE_RECITER.value, codenames)
        self.assertNotIn(PermissionChoice.PORTAL_UPDATE_RECITER.value, codenames)
        self.assertNotIn(PermissionChoice.PORTAL_DELETE_RECITER.value, codenames)

    def test_revoke_from_user_where_update_revoked_should_keep_sibling_writes_and_read(self):
        # Arrange
        self.service.grant_to_user(
            self.user,
            [
                PermissionChoice.PORTAL_CREATE_RECITER,
                PermissionChoice.PORTAL_UPDATE_RECITER,
                PermissionChoice.PORTAL_DELETE_RECITER,
            ],
        )

        # Act
        self.service.revoke_from_user(self.user, [PermissionChoice.PORTAL_UPDATE_RECITER])

        # Assert
        # UPDATE has no dependents of its own, so its siblings CREATE and DELETE survive.
        codenames = self._user_perm_codenames()
        self.assertIn(PermissionChoice.PORTAL_READ_RECITER.value, codenames)
        self.assertIn(PermissionChoice.PORTAL_CREATE_RECITER.value, codenames)
        self.assertIn(PermissionChoice.PORTAL_DELETE_RECITER.value, codenames)
        self.assertNotIn(PermissionChoice.PORTAL_UPDATE_RECITER.value, codenames)

    def test_revoke_from_user_where_permission_not_held_should_be_idempotent(self):
        # Arrange
        self.service.grant_to_user(self.user, [PermissionChoice.PORTAL_CREATE_RECITER])

        # Act
        self.service.revoke_from_user(self.user, [PermissionChoice.PORTAL_READ_RECITER])
        self.service.revoke_from_user(self.user, [PermissionChoice.PORTAL_READ_RECITER])

        # Assert
        self.assertEqual(self.user.user_permissions.count(), 0)

    def test_revoke_from_user_where_revoked_should_return_dependents_closure(self):
        # Arrange
        self.service.grant_to_user(self.user, [PermissionChoice.PORTAL_DELETE_RECITER])

        # Act
        removed = self.service.revoke_from_user(self.user, [PermissionChoice.PORTAL_READ_RECITER])

        # Assert
        self.assertEqual(
            removed,
            {
                PermissionChoice.PORTAL_READ_RECITER,
                PermissionChoice.PORTAL_CREATE_RECITER,
                PermissionChoice.PORTAL_UPDATE_RECITER,
                PermissionChoice.PORTAL_DELETE_RECITER,
            },
        )

    def test_revoke_from_group_where_read_revoked_should_remove_whole_group(self):
        # Arrange
        group = Group.objects.create(name="editors")
        self.service.grant_to_group(group, [PermissionChoice.PORTAL_DELETE_TRANSLATION])

        # Act
        self.service.revoke_from_group(group, [PermissionChoice.PORTAL_READ_TRANSLATION])

        # Assert
        self.assertEqual(group.permissions.count(), 0)
