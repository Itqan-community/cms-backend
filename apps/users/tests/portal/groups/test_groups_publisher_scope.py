import json

from django.contrib.auth.models import Group
from model_bakery import baker

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher, PublisherGroup, PublisherMember
from apps.publishers.tests.group_helpers import publisher_role
from apps.users.models import User


class GroupsPublisherScopeTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.publisher_a = baker.make(Publisher)
        self.publisher_b = baker.make(Publisher)
        self.user = baker.make(User, email="groups-admin@example.com")
        for permission in (
            PermissionChoice.PORTAL_CREATE_GROUP,
            PermissionChoice.PORTAL_READ_GROUP,
            PermissionChoice.PORTAL_UPDATE_GROUP,
            PermissionChoice.PORTAL_DELETE_GROUP,
        ):
            self.give_permission(self.user, permission)

    def _as(self, user: User, publisher: Publisher | None) -> None:
        extra = {"HTTP_X_TENANT": str(publisher.id)} if publisher else {}
        self.authenticate_user(user, **extra)

    def _set_permissions(self, group_id: int, permissions: list[str]):
        return self.client.put(
            f"/portal/groups/{group_id}/permissions/",
            json.dumps({"permissions": permissions}),
            content_type="application/json",
        )

    def test_list_returns_only_this_publishers_groups(self) -> None:
        publisher_role(self.publisher_a, "Editors")
        publisher_role(self.publisher_b, "Reviewers")
        self._as(self.user, self.publisher_a)

        response = self.client.get("/portal/groups/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["Editors"], [item["name"] for item in response.json()["results"]])

    def test_same_name_can_exist_in_two_publishers(self) -> None:
        self._as(self.user, self.publisher_a)
        first = self.client.post("/portal/groups/", {"name": "Editors"}, format="json")
        self._as(self.user, self.publisher_b)
        second = self.client.post("/portal/groups/", {"name": "Editors"}, format="json")

        self.assertEqual(201, first.status_code, first.content)
        self.assertEqual(201, second.status_code, second.content)

    def test_duplicate_name_within_publisher_is_400(self) -> None:
        publisher_role(self.publisher_a, "Editors")
        self._as(self.user, self.publisher_a)

        response = self.client.post("/portal/groups/", {"name": "Editors"}, format="json")

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_created_group_has_opaque_auth_name(self) -> None:
        self._as(self.user, self.publisher_a)

        response = self.client.post("/portal/groups/", {"name": "Editors"}, format="json")

        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("Editors", response.json()["name"])
        group = Group.objects.get(id=response.json()["id"])
        self.assertTrue(group.name.startswith(f"publisher:{self.publisher_a.id}:"))
        self.assertEqual(self.publisher_a.id, group.publisher_group.publisher_id)

    def test_rename_changes_only_the_display_name(self) -> None:
        group = publisher_role(self.publisher_a, "Editors")
        auth_name = group.name
        self._as(self.user, self.publisher_a)

        response = self.client.put(f"/portal/groups/{group.id}/", {"name": "Writers"}, format="json")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Writers", response.json()["name"])
        group.refresh_from_db()
        self.assertEqual(auth_name, group.name)
        self.assertEqual("Writers", PublisherGroup.objects.get(group=group).name)

    def test_other_publishers_group_is_404(self) -> None:
        group = publisher_role(self.publisher_b, "Editors")
        self._as(self.user, self.publisher_a)

        responses = [
            self.client.get(f"/portal/groups/{group.id}/"),
            self.client.put(f"/portal/groups/{group.id}/", {"name": "X"}, format="json"),
            self._set_permissions(group.id, []),
            self.client.delete(f"/portal/groups/{group.id}/"),
        ]

        for response in responses:
            self.assertEqual(404, response.status_code, response.content)
            self.assertEqual("group_not_found", response.json()["error_name"])
        self.assertTrue(Group.objects.filter(id=group.id).exists())

    def test_global_group_is_404(self) -> None:
        group = Group.objects.create(name="Legacy shared")
        self._as(self.user, self.publisher_a)

        response = self.client.get(f"/portal/groups/{group.id}/")

        self.assertEqual(404, response.status_code, response.content)

    def test_missing_tenant_is_400_tenant_required(self) -> None:
        self._as(self.user, None)

        response = self.client.get("/portal/groups/")

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("tenant_required", response.json()["error_name"])

    def test_editor_cannot_grant_permission_they_lack(self) -> None:
        editor = baker.make(User, email="publisher-admin@example.com")
        admin_role = publisher_role(
            self.publisher_a,
            "Admins",
            PermissionChoice.PORTAL_ACCESS,
            PermissionChoice.PORTAL_READ_GROUP,
            PermissionChoice.PORTAL_UPDATE_GROUP,
        )
        PublisherMember.objects.create(
            user=editor, publisher=self.publisher_a, group=admin_role, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._as(editor, self.publisher_a)

        response = self._set_permissions(admin_role.id, [PermissionChoice.PORTAL_CREATE_PUBLISHER.value])

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("permission_not_grantable", response.json()["error_name"])
        self.assertNotIn(
            PermissionChoice.PORTAL_CREATE_PUBLISHER.value,
            set(admin_role.permissions.values_list("codename", flat=True)),
        )

    def test_editor_can_grant_permissions_they_hold(self) -> None:
        editor = baker.make(User, email="publisher-admin2@example.com")
        admin_role = publisher_role(
            self.publisher_a, "Admins", PermissionChoice.PORTAL_UPDATE_GROUP, PermissionChoice.PORTAL_READ_RECITER
        )
        target = publisher_role(self.publisher_a, "Readers")
        PublisherMember.objects.create(
            user=editor, publisher=self.publisher_a, group=admin_role, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._as(editor, self.publisher_a)

        response = self._set_permissions(target.id, [PermissionChoice.PORTAL_READ_RECITER.value])

        self.assertEqual(200, response.status_code, response.content)

    def test_editor_can_edit_role_that_already_holds_permission_they_lack(self) -> None:
        editor = baker.make(User, email="publisher-admin3@example.com")
        admin_role = publisher_role(
            self.publisher_a, "Admins", PermissionChoice.PORTAL_UPDATE_GROUP, PermissionChoice.PORTAL_READ_RECITER
        )
        # Staff granted this role a permission the editor doesn't hold.
        target = publisher_role(self.publisher_a, "Managers", PermissionChoice.PORTAL_CREATE_PUBLISHER)
        PublisherMember.objects.create(
            user=editor, publisher=self.publisher_a, group=admin_role, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._as(editor, self.publisher_a)

        response = self._set_permissions(
            target.id,
            [PermissionChoice.PORTAL_CREATE_PUBLISHER.value, PermissionChoice.PORTAL_READ_RECITER.value],
        )

        self.assertEqual(200, response.status_code, response.content)

    def test_staff_can_grant_any_permission(self) -> None:
        staff = baker.make(User, email="staff@example.com", is_staff=True)
        self.give_permission(staff, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = publisher_role(self.publisher_a, "Admins")
        self._as(staff, self.publisher_a)

        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_CREATE_PUBLISHER.value])

        self.assertEqual(200, response.status_code, response.content)

    def test_delete_group_in_use_is_400_group_in_use(self) -> None:
        group = publisher_role(self.publisher_a, "Editors")
        PublisherMember.objects.create(
            user=baker.make(User, email="member@example.com"), publisher=self.publisher_a, group=group
        )
        self._as(self.user, self.publisher_a)

        response = self.client.delete(f"/portal/groups/{group.id}/")

        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_in_use", response.json()["error_name"])
        self.assertTrue(Group.objects.filter(id=group.id).exists())

    def test_delete_unused_group_removes_role_and_auth_group(self) -> None:
        group = publisher_role(self.publisher_a, "Editors")
        self._as(self.user, self.publisher_a)

        response = self.client.delete(f"/portal/groups/{group.id}/")

        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Group.objects.filter(id=group.id).exists())
        self.assertFalse(PublisherGroup.objects.filter(group_id=group.id).exists())
