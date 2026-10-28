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

    def test_list_groups_where_two_publishers_should_return_only_tenants_groups(self) -> None:
        # Arrange
        publisher_role(self.publisher_a, "Editors")
        publisher_role(self.publisher_b, "Reviewers")
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.get("/portal/groups/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["Editors"], [item["name"] for item in response.json()["results"]])

    def test_create_group_where_same_name_in_two_publishers_should_return_201(self) -> None:
        # Arrange
        self._as(self.user, self.publisher_a)
        first = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "Editors"}, format="json")
        self._as(self.user, self.publisher_b)
        second = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Act & Assert
        self.assertEqual(201, first.status_code, first.content)
        self.assertEqual(201, second.status_code, second.content)

    def test_create_group_where_duplicate_name_in_publisher_should_return_400(self) -> None:
        # Arrange
        publisher_role(self.publisher_a, "Editors")
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_create_group_where_created_should_use_opaque_auth_name(self) -> None:
        # Arrange
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "Editors"}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        self.assertEqual("Editors", response.json()["name"])
        group = Group.objects.get(id=response.json()["id"])
        self.assertTrue(group.name.startswith(f"publisher:{self.publisher_a.id}:"))
        self.assertEqual(self.publisher_a.id, group.publisher_group.publisher_id)

    def test_update_group_where_renamed_should_change_only_display_name(self) -> None:
        # Arrange
        group = publisher_role(self.publisher_a, "Editors")
        auth_name = group.name
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/", {"name_en": "Writers", "name_ar": "Writers"}, format="json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Writers", response.json()["name"])
        group.refresh_from_db()
        self.assertEqual(auth_name, group.name)
        self.assertEqual("Writers", PublisherGroup.objects.get(group=group).name)

    def test_group_endpoints_where_group_belongs_to_other_publisher_should_return_404(self) -> None:
        # Arrange
        group = publisher_role(self.publisher_b, "Editors")
        self._as(self.user, self.publisher_a)

        # Act
        responses = [
            self.client.get(f"/portal/groups/{group.id}/"),
            self.client.put(f"/portal/groups/{group.id}/", {"name_en": "X", "name_ar": "X"}, format="json"),
            self._set_permissions(group.id, []),
            self.client.delete(f"/portal/groups/{group.id}/"),
        ]

        # Assert
        for response in responses:
            self.assertEqual(404, response.status_code, response.content)
            self.assertEqual("group_not_found", response.json()["error_name"])
        self.assertTrue(Group.objects.filter(id=group.id).exists())

    def test_retrieve_group_where_group_is_global_should_return_404(self) -> None:
        # Arrange
        group = Group.objects.create(name="Legacy shared")
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.get(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)

    def test_list_groups_where_no_tenant_should_return_400(self) -> None:
        # Arrange
        self._as(self.user, None)

        # Act
        response = self.client.get("/portal/groups/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("tenant_required", response.json()["error_name"])

    def test_set_permissions_where_editor_lacks_permission_should_return_400(self) -> None:
        # Arrange
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

        # Act
        response = self._set_permissions(admin_role.id, [PermissionChoice.PORTAL_CREATE_PUBLISHER.value])

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("permission_not_grantable", response.json()["error_name"])
        self.assertNotIn(
            PermissionChoice.PORTAL_CREATE_PUBLISHER.value,
            set(admin_role.permissions.values_list("codename", flat=True)),
        )

    def test_set_permissions_where_editor_holds_permission_should_return_200(self) -> None:
        # Arrange
        editor = baker.make(User, email="publisher-admin2@example.com")
        admin_role = publisher_role(
            self.publisher_a, "Admins", PermissionChoice.PORTAL_UPDATE_GROUP, PermissionChoice.PORTAL_READ_RECITER
        )
        target = publisher_role(self.publisher_a, "Readers")
        PublisherMember.objects.create(
            user=editor, publisher=self.publisher_a, group=admin_role, status=PublisherMember.StatusChoice.ACTIVE
        )
        self._as(editor, self.publisher_a)

        # Act
        response = self._set_permissions(target.id, [PermissionChoice.PORTAL_READ_RECITER.value])

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_set_permissions_where_role_already_holds_unheld_permission_should_return_200(self) -> None:
        # Arrange
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

        # Act
        response = self._set_permissions(
            target.id,
            [PermissionChoice.PORTAL_CREATE_PUBLISHER.value, PermissionChoice.PORTAL_READ_RECITER.value],
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_set_permissions_where_editor_is_staff_should_return_200(self) -> None:
        # Arrange
        staff = baker.make(User, email="staff@example.com", is_staff=True)
        self.give_permission(staff, PermissionChoice.PORTAL_UPDATE_GROUP)
        group = publisher_role(self.publisher_a, "Admins")
        self._as(staff, self.publisher_a)

        # Act
        response = self._set_permissions(group.id, [PermissionChoice.PORTAL_CREATE_PUBLISHER.value])

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_delete_group_where_assigned_to_members_should_return_400(self) -> None:
        # Arrange
        group = publisher_role(self.publisher_a, "Editors")
        PublisherMember.objects.create(
            user=baker.make(User, email="member@example.com"), publisher=self.publisher_a, group=group
        )
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.delete(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_in_use", response.json()["error_name"])
        self.assertTrue(Group.objects.filter(id=group.id).exists())

    def test_delete_group_where_unused_should_remove_role_and_auth_group(self) -> None:
        # Arrange
        group = publisher_role(self.publisher_a, "Editors")
        self._as(self.user, self.publisher_a)

        # Act
        response = self.client.delete(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Group.objects.filter(id=group.id).exists())
        self.assertFalse(PublisherGroup.objects.filter(group_id=group.id).exists())


class GroupsBilingualTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = baker.make(User, email="bilingual@example.com", is_staff=True)
        for permission in (
            PermissionChoice.PORTAL_CREATE_GROUP,
            PermissionChoice.PORTAL_READ_GROUP,
            PermissionChoice.PORTAL_UPDATE_GROUP,
        ):
            self.give_permission(self.user, permission)

    def _as(self, language: str) -> None:
        self.authenticate_user(self.user, language=language, HTTP_X_TENANT=str(self.publisher.id))

    def test_create_group_where_both_names_given_should_return_them_and_localized_name(self) -> None:
        # Arrange
        self._as("ar")

        # Act
        response = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "المحررون"}, format="json")

        # Assert
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        self.assertEqual(("المحررون", "Editors", "المحررون"), (body["name"], body["name_en"], body["name_ar"]))

    def test_create_group_where_arabic_name_blank_should_return_400(self) -> None:
        # Arrange
        self._as("en")

        # Act
        response = self.client.post("/portal/groups/", {"name_en": "Editors", "name_ar": "  "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_name_required", response.json()["error_name"])

    def test_create_group_where_arabic_name_taken_in_publisher_should_return_400(self) -> None:
        # Arrange
        publisher_role(self.publisher, "Editors", name_ar="المحررون")
        self._as("en")

        # Act
        response = self.client.post("/portal/groups/", {"name_en": "Writers", "name_ar": "المحررون"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("group_already_exists", response.json()["error_name"])

    def test_update_group_where_renamed_should_change_both_names(self) -> None:
        # Arrange
        group = publisher_role(self.publisher, "Editors", name_ar="المحررون")
        self._as("en")

        # Act
        response = self.client.put(
            f"/portal/groups/{group.id}/", {"name_en": "Writers", "name_ar": "الكتّاب"}, format="json"
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        role = PublisherGroup.objects.get(group=group)
        self.assertEqual(("Writers", "الكتّاب"), (role.name_en, role.name_ar))

    def test_list_groups_where_searching_arabic_name_should_match(self) -> None:
        # Arrange
        publisher_role(self.publisher, "Editors", name_ar="المحررون")
        publisher_role(self.publisher, "Readers", name_ar="القراء")
        self._as("ar")

        # Act
        response = self.client.get("/portal/groups/", {"search": "المحرر"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["المحررون"], [item["name"] for item in response.json()["results"]])

    def test_list_groups_where_ordered_by_arabic_name_should_sort_by_it(self) -> None:
        # Arrange
        publisher_role(self.publisher, "A role", name_ar="ي")
        publisher_role(self.publisher, "B role", name_ar="أ")
        self._as("ar")

        # Act
        response = self.client.get("/portal/groups/", {"ordering": "name_ar"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(["أ", "ي"], [item["name_ar"] for item in response.json()["results"]])

    def test_list_permissions_where_arabic_should_return_arabic_labels(self) -> None:
        # Arrange
        self._as("ar")

        # Act
        response = self.client.get("/portal/groups/permissions/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        by_code = {p["code_name"]: p["name"] for group in response.json() for p in group["permissions"]}
        self.assertEqual(set(PermissionChoice.values), set(by_code))
        self.assertEqual("لوحة التحكم - عرض القراء", by_code[PermissionChoice.PORTAL_READ_RECITER.value])

    def test_retrieve_group_where_arabic_should_return_permission_labels_in_arabic(self) -> None:
        # Arrange
        group = publisher_role(self.publisher, "Readers", PermissionChoice.PORTAL_READ_RECITER, name_ar="القراء")
        self._as("ar")

        # Act
        response = self.client.get(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(
            [{"code_name": "portal_read_reciter", "name": "لوحة التحكم - عرض القراء"}], response.json()["permissions"]
        )


class PermissionCatalogueGroupsTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = baker.make(User, email="catalogue@example.com", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)

    def _get(self, language: str):
        self.authenticate_user(self.user, language=language, HTTP_X_TENANT=str(self.publisher.id))
        return self.client.get("/portal/groups/permissions/")

    def test_list_permissions_where_requested_should_group_every_permission_exactly_once(self) -> None:
        # Arrange & Act
        response = self._get("en")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        codes = [p["code_name"] for group in response.json() for p in group["permissions"]]
        self.assertEqual(sorted(PermissionChoice.values), sorted(codes))

    def test_list_permissions_where_arabic_should_name_groups_in_arabic(self) -> None:
        # Arrange & Act
        response = self._get("ar")

        # Assert
        names = {group["key"]: group["name"] for group in response.json()}
        self.assertEqual("القراء", names["reciters"])
        self.assertEqual("الأدوار", names["roles"])

    def test_list_permissions_where_permission_implies_others_should_list_full_closure(self) -> None:
        # Arrange & Act
        response = self._get("en")

        # Assert
        implies = {p["code_name"]: set(p["implies"]) for group in response.json() for p in group["permissions"]}
        self.assertEqual(
            {"portal_read_reciter", "portal_create_reciter", "portal_update_reciter"}, implies["portal_delete_reciter"]
        )
        self.assertEqual(
            {"portal_update_recitation", "portal_create_recitation", "portal_read_recitation"},
            implies["portal_upload_timing"],
        )
        self.assertEqual(set(), implies["portal_access"])

    def test_list_permissions_where_arabic_should_say_control_panel_never_portal(self) -> None:
        # Arrange & Act
        response = self._get("ar")

        # Assert
        names = [p["name"] for group in response.json() for p in group["permissions"]]
        self.assertFalse([name for name in names if "البوابة" in name])
        self.assertIn("لوحة التحكم - عرض الأدوار", names)


class GroupPermissionCountTest(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.publisher = baker.make(Publisher)
        self.user = baker.make(User, email="counts@example.com", is_staff=True)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_GROUP)

    def test_list_groups_where_roles_hold_permissions_should_return_each_count(self) -> None:
        # Arrange
        publisher_role(self.publisher, "Readers", PermissionChoice.PORTAL_READ_RECITER)
        publisher_role(
            self.publisher, "Editors", PermissionChoice.PORTAL_READ_RECITER, PermissionChoice.PORTAL_CREATE_RECITER
        )
        publisher_role(self.publisher, "Empty")
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get("/portal/groups/", {"ordering": "name_en"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        counts = {item["name_en"]: item["permissions_count"] for item in response.json()["results"]}
        self.assertEqual({"Editors": 2, "Empty": 0, "Readers": 1}, counts)

    def test_list_groups_where_more_roles_should_keep_query_count(self) -> None:
        # Arrange
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        def count() -> int:
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get("/portal/groups/")
            self.assertEqual(200, response.status_code, response.content)
            return len(ctx.captured_queries)

        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher.id))
        publisher_role(self.publisher, "One", PermissionChoice.PORTAL_READ_RECITER)
        count()
        one = count()
        for name in ("Two", "Three", "Four"):
            publisher_role(self.publisher, name, PermissionChoice.PORTAL_READ_RECITER)

        # Act & Assert
        self.assertEqual(one, count())

    def test_retrieve_group_where_role_holds_permissions_should_return_count(self) -> None:
        # Arrange
        group = publisher_role(self.publisher, "Readers", PermissionChoice.PORTAL_READ_RECITER)
        self.authenticate_user(self.user, HTTP_X_TENANT=str(self.publisher.id))

        # Act
        response = self.client.get(f"/portal/groups/{group.id}/")

        # Assert
        self.assertEqual(1, response.json()["permissions_count"])
