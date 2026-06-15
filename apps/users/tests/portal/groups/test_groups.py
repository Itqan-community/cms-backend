import json

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class CreateGroupTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/groups/"

    def test_create_group_where_name_provided_should_return_201(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)

        # Act
        response = self.client.post(self.url, {"name": "Editors"}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Editors", body["name"])
        self.assertEqual([], body["permissions"])
        self.assertTrue(Group.objects.filter(name="Editors").exists())

    def test_create_group_where_name_empty_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)

        # Act
        response = self.client.post(self.url, {"name": "   "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_name_required", response.json()["error_name"])

    def test_create_group_where_duplicate_name_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)
        baker.make(Group, name="Editors")

        # Act
        response = self.client.post(self.url, {"name": "Editors"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_create_group_where_unauthenticated_should_return_401(self) -> None:
        # Arrange / Act
        response = self.client.post(self.url, {"name": "Editors"}, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_create_group_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self.url, {"name": "Editors"}, format="json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class ListGroupTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)
        self.url = "/portal/groups/"

    def test_list_groups_where_groups_exist_should_return_them(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        baker.make(Group, name="Editors")
        baker.make(Group, name="Reviewers")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = {item["name"] for item in response.json()["results"]}
        self.assertGreaterEqual(names, {"Editors", "Reviewers"})

    def test_list_groups_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class RetrieveGroupTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def test_retrieve_group_where_exists_should_return_200(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.get(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Editors", body["name"])
        self.assertIn("permissions", body)

    def test_retrieve_group_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)

        # Act
        response = self.client.get("/portal/groups/999999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("group_not_found", response.json()["error_name"])


class UpdateGroupTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def test_update_group_where_renamed_should_return_200(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/", json.dumps({"name": "Senior Editors"}), content_type="application/json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Senior Editors", response.json()["name"])
        group.refresh_from_db()
        self.assertEqual("Senior Editors", group.name)

    def test_update_group_where_duplicate_name_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        baker.make(Group, name="Reviewers")
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/", json.dumps({"name": "Reviewers"}), content_type="application/json"
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_update_group_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)

        # Act
        response = self.client.put("/portal/groups/999999/", json.dumps({"name": "X"}), content_type="application/json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("group_not_found", response.json()["error_name"])


class SetGroupPermissionsTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def _set_permissions(self, group_id: int, permissions: list[str]):
        return self.client.put(
            f"/portal/groups/{group_id}/permissions/",
            json.dumps({"permissions": permissions}),
            content_type="application/json",
        )

    def test_set_permissions_where_create_given_should_apply_implied_read(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = baker.make(Group, name="Editors")

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_CREATE_RECITER.value])

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {
                PermissionChoice.PORTAL_CREATE_RECITER.value,
                PermissionChoice.PORTAL_READ_RECITER.value,
            },
            set(response.json()["permissions"]),
        )
        stored = {perm.codename for perm in group.permissions.all()}
        self.assertEqual(
            {PermissionChoice.PORTAL_CREATE_RECITER.value, PermissionChoice.PORTAL_READ_RECITER.value},
            stored,
        )

    def test_set_permissions_where_called_again_should_replace_not_accumulate(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = baker.make(Group, name="Editors")
        self._set_permissions(group.id, [PermissionChoice.PORTAL_DELETE_RECITER.value])

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_READ_TAFSIR.value])

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {PermissionChoice.PORTAL_READ_TAFSIR.value},
            set(response.json()["permissions"]),
        )

    def test_set_permissions_where_empty_list_should_clear_permissions(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = baker.make(Group, name="Editors")
        self._set_permissions(group.id, [PermissionChoice.PORTAL_CREATE_RECITER.value])

        # Act
        response = self._set_permissions(group.id, [])

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json()["permissions"])
        self.assertEqual(0, group.permissions.count())

    def test_set_permissions_where_unknown_permission_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = baker.make(Group, name="Editors")

        # Act
        response = self._set_permissions(group.id, ["not_a_real_permission"])

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_permission", response.json()["error_name"])

    def test_set_permissions_where_group_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)

        # Act
        response = self._set_permissions(999999, [PermissionChoice.PORTAL_READ_RECITER.value])

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("group_not_found", response.json()["error_name"])

    def test_set_permissions_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        group = baker.make(Group, name="Editors")

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_READ_RECITER.value])

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class DeleteGroupTest(BaseTestCase):
    def setUp(self) -> None:
        self.user = baker.make(User)

    def test_delete_group_where_exists_should_return_204(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_GROUP)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.delete(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Group.objects.filter(id=group.id).exists())

    def test_delete_group_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_GROUP)

        # Act
        response = self.client.delete("/portal/groups/999999/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("group_not_found", response.json()["error_name"])

    def test_delete_group_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.delete(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])
