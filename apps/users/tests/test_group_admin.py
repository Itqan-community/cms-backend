from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker
from plain_permissions.models import Permission as CustomPermission

from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


def permission_row(codename: PermissionChoice | str) -> Permission:
    """Resolve a managed permission codename to its Django ``Permission`` row."""
    content_type = ContentType.objects.get_for_model(CustomPermission)
    return Permission.objects.get(content_type=content_type, codename=str(codename))


class GroupAdminSaveTest(BaseTestCase):
    def setUp(self) -> None:
        self.superuser = baker.make(User, is_staff=True, is_superuser=True)
        self.add_url = reverse("admin:auth_group_add")

    def test_save_model_where_permission_implies_another_should_store_implied_closure(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        create_group = permission_row(PermissionChoice.PORTAL_CREATE_GROUP)

        # Act
        response = self.client.post(
            self.add_url,
            {"name": "Editors", "permissions": [create_group.pk]},
        )

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        group = Group.objects.get(name="Editors")
        stored = set(group.permissions.values_list("codename", flat=True))
        self.assertIn(PermissionChoice.PORTAL_CREATE_GROUP.value, stored)
        self.assertIn(PermissionChoice.PORTAL_READ_GROUP.value, stored)

    def test_save_model_where_no_permissions_selected_should_store_none(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        response = self.client.post(self.add_url, {"name": "Editors", "permissions": []})

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        group = Group.objects.get(name="Editors")
        self.assertEqual(0, group.permissions.count())

    def test_save_model_where_name_has_whitespace_should_store_trimmed_name(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)

        # Act
        response = self.client.post(self.add_url, {"name": "  Editors  ", "permissions": []})

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        self.assertTrue(Group.objects.filter(name="Editors").exists())

    def test_save_model_where_unmanaged_permission_selected_should_reject_it(self) -> None:
        # Arrange
        # The form's queryset is limited to the managed plain_permissions rows, so Django's
        # built-in permissions are not offered as choices and cannot be assigned here.
        self.client.force_login(self.superuser)
        unmanaged = Permission.objects.exclude(content_type=ContentType.objects.get_for_model(CustomPermission)).first()
        assert unmanaged is not None

        # Act
        response = self.client.post(
            self.add_url,
            {"name": "Editors", "permissions": [unmanaged.pk]},
        )

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertFalse(Group.objects.filter(name="Editors").exists())


class GroupAdminValidationTest(BaseTestCase):
    def setUp(self) -> None:
        self.superuser = baker.make(User, is_staff=True, is_superuser=True)
        self.add_url = reverse("admin:auth_group_add")

    def test_clean_name_where_duplicate_should_show_form_error_and_not_create(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        baker.make(Group, name="Editors")

        # Act
        response = self.client.post(self.add_url, {"name": "Editors", "permissions": []})

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "A group with this name already exists.")
        self.assertEqual(1, Group.objects.filter(name="Editors").count())

    def test_clean_name_where_blank_should_show_form_error_and_not_create(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        existing_ids = set(Group.objects.values_list("pk", flat=True))

        # Act
        response = self.client.post(self.add_url, {"name": "   ", "permissions": []})

        # Assert
        self.assertEqual(200, response.status_code)
        self.assertEqual(existing_ids, set(Group.objects.values_list("pk", flat=True)))

    def test_clean_name_where_renaming_to_own_name_should_succeed(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.post(
            reverse("admin:auth_group_change", args=[group.pk]),
            {"name": "Editors", "permissions": []},
        )

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        group.refresh_from_db()
        self.assertEqual("Editors", group.name)


class GroupAdminDeleteTest(BaseTestCase):
    def setUp(self) -> None:
        self.superuser = baker.make(User, is_staff=True, is_superuser=True)

    def test_delete_model_where_confirmed_should_delete_group(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        group = baker.make(Group, name="Editors")

        # Act
        response = self.client.post(reverse("admin:auth_group_delete", args=[group.pk]), {"post": "yes"})

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())

    def test_delete_queryset_where_bulk_action_should_delete_all_selected(self) -> None:
        # Arrange
        self.client.force_login(self.superuser)
        first = baker.make(Group, name="Editors")
        second = baker.make(Group, name="Reviewers")

        # Act
        response = self.client.post(
            reverse("admin:auth_group_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [first.pk, second.pk],
                "post": "yes",
            },
        )

        # Assert
        self.assertEqual(302, response.status_code, response.content)
        self.assertFalse(Group.objects.filter(pk__in=[first.pk, second.pk]).exists())
