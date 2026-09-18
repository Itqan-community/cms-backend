from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class MushafLayoutsApiTests(BaseTestCase):
    def test_list_where_layouts_exist_should_return_them(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)
        baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.get("/portal/mushaf-layouts/")

        # Assert
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["results"]]
        self.assertIn("Madani 604", names)

    def test_create_where_valid_should_return_201_and_persist(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT)

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"name_en": "Indo-Pak 611", "name_ar": "الهندي ٦١١", "page_count": 611},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        self.assertTrue(MushafLayout.objects.filter(page_count=611).exists())

    def test_create_where_duplicate_name_should_return_409_with_error_name(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT)
        baker.make(MushafLayout, name_en="Madani 604", name_ar="مدني 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"name_en": "Madani 604", "name_ar": "مدني 604", "page_count": 604},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_already_exists")

    def test_create_where_names_blank_should_return_400_with_error_name(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT)

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"page_count": 5},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_name_required")

    def test_retrieve_where_layout_missing_should_return_404_with_error_name(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)

        # Act
        response = self.client.get("/portal/mushaf-layouts/999999/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_update_where_valid_should_return_200_and_persist(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT)
        layout = baker.make(MushafLayout, name_en="Madani 604", name_ar="مدني 604", page_count=604)

        # Act
        response = self.client.patch(
            f"/portal/mushaf-layouts/{layout.pk}/",
            data={"page_count": 605},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        layout.refresh_from_db()
        self.assertEqual(layout.page_count, 605)

    def test_update_where_layout_missing_should_return_404_with_error_name(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT)

        # Act
        response = self.client.patch(
            "/portal/mushaf-layouts/999999/",
            data={"page_count": 605},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_delete_where_layout_in_use_should_return_400_with_error_name(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        response = self.client.delete(f"/portal/mushaf-layouts/{layout.pk}/")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_in_use")

    def test_delete_where_layout_unused_should_return_204_and_remove_it(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.delete(f"/portal/mushaf-layouts/{layout.pk}/")

        # Assert
        self.assertEqual(response.status_code, 204)
        self.assertFalse(MushafLayout.objects.filter(pk=layout.pk).exists())

    def test_create_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"name_en": "Nope", "page_count": 1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_update_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.patch(
            f"/portal/mushaf-layouts/{layout.pk}/",
            data={"page_count": 605},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_delete_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.delete(f"/portal/mushaf-layouts/{layout.pk}/")

        # Assert
        self.assertEqual(response.status_code, 403)

    def test_list_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.user = User.objects.create_user(email="admin@example.com", name="Admin", is_staff=True)
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/portal/mushaf-layouts/")

        # Assert
        self.assertEqual(response.status_code, 403)
