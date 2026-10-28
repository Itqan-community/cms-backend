import json

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup
from apps.publishers.tests.group_helpers import publisher_role
from apps.users.models import User
from apps.users.services.group import ITQAN_INTERNAL_GROUP


class GroupsApiTestCase(BaseTestCase):
    """Groups are per-publisher roles: requests carry the publisher in X-Tenant."""

    def setUp(self) -> None:
        super().setUp()
        self.publisher = baker.make(Publisher)

    def authenticate_user(self, user, *args, **kwargs):
        if user is not None:
            kwargs.setdefault("HTTP_X_TENANT", str(self.publisher.id))
        return super().authenticate_user(user, *args, **kwargs)

    def make_group(self, name: str) -> Group:
        return publisher_role(self.publisher, name)


class CreateGroupTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User)
        self.url = "/portal/groups/"

    def test_create_group_where_name_provided_should_return_201(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)

        # Act
        response = self.client.post(self.url, {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual("Editors", body["name"])
        self.assertEqual([], body["permissions"])
        self.assertTrue(PublisherGroup.objects.filter(publisher=self.publisher, name="Editors").exists())

    def test_create_group_where_name_empty_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)

        # Act
        response = self.client.post(self.url, {"name_en": "   ", "name_ar": "   "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_name_required", response.json()["error_name"])

    def test_create_group_where_duplicate_name_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_GROUP)
        self.make_group(name="Editors")

        # Act
        response = self.client.post(self.url, {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_create_group_where_unauthenticated_should_return_401(self) -> None:
        # Arrange / Act
        response = self.client.post(self.url, {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_create_group_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.post(self.url, {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class ListGroupTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User)
        self.url = "/portal/groups/"

    def test_list_groups_where_groups_exist_should_return_them(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        self.make_group(name="Editors")
        self.make_group(name="Reviewers")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = {item["name"] for item in response.json()["results"]}
        self.assertGreaterEqual(names, {"Editors", "Reviewers"})

    def test_list_groups_where_itqan_internal_exists_should_exclude_it(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)
        self.make_group(name="Editors")

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = {item["name"] for item in response.json()["results"]}
        self.assertIn("Editors", names)
        self.assertNotIn(ITQAN_INTERNAL_GROUP, names)

    def test_list_groups_where_staff_user_should_still_exclude_itqan_internal(self) -> None:
        # Arrange: hidden for everyone, staff included.
        staff = baker.make(User, is_staff=True)
        self.authenticate_user(staff)
        self.give_permission(staff, PermissionChoice.PORTAL_READ_GROUP)
        Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = {item["name"] for item in response.json()["results"]}
        self.assertNotIn(ITQAN_INTERNAL_GROUP, names)

    def test_list_groups_where_searching_for_itqan_internal_should_return_nothing(self) -> None:
        # Arrange: the exclusion must survive the search filter, not just the plain listing.
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        Group.objects.get_or_create(name=ITQAN_INTERNAL_GROUP)

        # Act
        response = self.client.get(self.url, {"search": "Itqan"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        names = {item["name"] for item in response.json()["results"]}
        self.assertNotIn(ITQAN_INTERNAL_GROUP, names)

    def test_list_groups_where_no_permission_should_return_403(self) -> None:
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get(self.url)

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class RetrieveGroupTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User)

    def test_retrieve_group_where_exists_should_return_200(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)
        group = self.make_group(name="Editors")

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


class UpdateGroupTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User)

    def test_update_group_where_renamed_should_return_200(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = self.make_group(name="Editors")

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/",
            json.dumps({"name_en": "Senior Editors", "name_ar": "Senior Editors"}),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Senior Editors", response.json()["name"])
        self.assertEqual("Senior Editors", PublisherGroup.objects.get(group=group).name)

    def test_update_group_where_duplicate_name_should_return_400(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        self.make_group(name="Reviewers")
        group = self.make_group(name="Editors")

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/",
            json.dumps({"name_en": "Reviewers", "name_ar": "Reviewers"}),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_update_group_where_not_found_should_return_404(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)

        # Act
        response = self.client.put(
            "/portal/groups/999999/", json.dumps({"name_en": "X", "name_ar": "X"}), content_type="application/json"
        )

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("group_not_found", response.json()["error_name"])


class SetGroupPermissionsTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Staff, so the grant ceiling (see test_groups_publisher_scope) doesn't apply here.
        self.user = baker.make(User, is_staff=True)

    def _set_permissions(self, group_id: int, permissions: list[str]):
        return self.client.put(
            f"/portal/groups/{group_id}/permissions/",
            json.dumps({"permissions": permissions}),
            content_type="application/json",
        )

    def test_set_permissions_where_create_given_should_apply_implied_read_and_update(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = self.make_group(name="Editors")

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_CREATE_RECITER.value])

        # Assert
        # CREATE and UPDATE are mutually implied, so both land alongside READ.
        expected = {
            PermissionChoice.PORTAL_CREATE_RECITER.value,
            PermissionChoice.PORTAL_UPDATE_RECITER.value,
            PermissionChoice.PORTAL_READ_RECITER.value,
        }
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(expected, {p["code_name"] for p in response.json()["permissions"]})
        stored = {perm.codename for perm in group.permissions.all()}
        self.assertEqual(expected, stored)

    def test_set_permissions_where_called_again_should_replace_not_accumulate(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = self.make_group(name="Editors")
        self._set_permissions(group.id, [PermissionChoice.PORTAL_DELETE_RECITER.value])

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_READ_TAFSIR.value])

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            {PermissionChoice.PORTAL_READ_TAFSIR.value},
            {p["code_name"] for p in response.json()["permissions"]},
        )

    def test_set_permissions_where_empty_list_should_clear_permissions(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = self.make_group(name="Editors")
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
        group = self.make_group(name="Editors")

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
        group = self.make_group(name="Editors")

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_READ_RECITER.value])

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])


class DeleteGroupTest(GroupsApiTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = baker.make(User)

    def test_delete_group_where_exists_should_return_204(self) -> None:
        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_GROUP)
        group = self.make_group(name="Editors")

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
        group = self.make_group(name="Editors")

        # Act
        response = self.client.delete(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])
