from django.utils.crypto import get_random_string

from apps.core.tests.base import BaseTestCase
from apps.users.models import User


class AuthEndpointsTestCase(BaseTestCase):
    """Test case for authentication endpoints"""

    def setUp(self):
        # randomize the test password to avoid Bandit B106
        self.user_password = get_random_string(16)
        self.user_data = {
            "email": "test@example.com",
            "password": self.user_password,
            "name": "Test User",
        }
        self.user = User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_password,
            name=self.user_data["name"],
        )


class UserProfileTestCase(BaseTestCase):
    """Tests for user profile endpoints"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="test@example.com")

    def test_get_profile_where_authenticated_user_should_return_200_with_profile_data(
        self,
    ):
        """Test successful profile retrieval for authenticated user"""
        # Arrange
        self.authenticate_user(user=self.user)

        # Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check response structure
        self.assertEqual(self.user.email, response_data["email"])
        self.assertEqual(self.user.name, response_data["name"])
        self.assertEqual(str(self.user.id), response_data["id"])
        self.assertTrue(response_data["is_active"])
        self.assertIn("created_at", response_data)
        self.assertIn("updated_at", response_data)
        self.assertIsNone(response_data["phone"])  # Phone should be None initially

    def test_get_profile_where_unauthenticated_should_return_401(self):
        """Test profile retrieval without authentication returns error"""
        # Arrange & Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_get_profile_where_invalid_token_should_return_401(self):
        """Test profile retrieval with invalid token returns error"""
        # Construct a clearly invalid JWT-like string without hardcoding a full token (avoid B105)
        invalid_token = ".".join(
            [
                "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # header
                "invalid",  # payload
                "signature",  # signature
            ]
        )
        response = self.client.get("/cms-api/auth/profile/", {"HTTP_AUTHORIZATION": f"Bearer {invalid_token}"})

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_update_profile_where_valid_data_should_return_200_with_updated_profile(
        self,
    ):
        """Test successful profile update with valid data"""
        # Arrange
        self.authenticate_user(user=self.user)

        data = {
            "bio": "Updated bio",
            "project_summary": "Updated Project Summary",
        }

        # Act
        response = self.client.put("/cms-api/auth/profile/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check updated data
        self.assertEqual(data["bio"], response_data["bio"])
        self.assertEqual(data["project_summary"], response_data["project_summary"])

        # Verify database update
        self.user.refresh_from_db()
        self.assertEqual(data["bio"], self.user.developer_profile.bio)
        self.assertEqual(data["project_summary"], str(self.user.developer_profile.project_summary))

    def test_update_profile_where_partial_data_should_return_200_with_partial_update(
        self,
    ):
        """Test partial profile update with only some fields"""
        # Arrange
        self.authenticate_user(user=self.user)

        data = {"bio": "Only bio updated"}

        # Act
        response = self.client.put("/cms-api/auth/profile/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check updated data
        self.assertEqual(data["bio"], response_data["bio"])
        # Other fields should remain unchanged
        self.assertEqual("", response_data["project_summary"])
        self.assertEqual("", response_data["project_url"])

    def test_update_profile_where_unauthenticated_should_return_401(self):
        """Test profile update without authentication returns error"""
        # Arrange
        data = {"name": "Should Not Update"}

        # Act
        response = self.client.put("/cms-api/auth/profile/", data=data, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_get_profile_where_user_has_no_permissions_should_return_empty_permissions_list(self):
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json()["permissions"])

    def test_get_profile_where_user_has_direct_permissions_should_return_them(self):
        from apps.core.permissions import PermissionChoice

        # Arrange
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_TAFSIR)
        self.give_permission(self.user, PermissionChoice.PORTAL_CREATE_TAFSIR)

        # Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        permissions = response.json()["permissions"]
        self.assertEqual(2, len(permissions))

        permission_codes = [p["code_name"] for p in permissions]
        self.assertIn(PermissionChoice.PORTAL_READ_TAFSIR, permission_codes)
        self.assertIn(PermissionChoice.PORTAL_CREATE_TAFSIR, permission_codes)
        # Should not include unassigned permissions
        self.assertNotIn(PermissionChoice.PORTAL_DELETE_TAFSIR, permission_codes)

    def test_get_profile_where_user_has_group_permissions_should_return_them(self):
        from django.contrib.auth.models import Group, Permission

        from apps.core.permissions import PermissionChoice

        # Arrange
        self.authenticate_user(self.user)
        group = Group.objects.create(name="Editors")
        group.permissions.add(Permission.objects.get(codename=PermissionChoice.PORTAL_UPDATE_TRANSLATION))
        self.user.groups.add(group)

        # Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        permissions = response.json()["permissions"]
        self.assertEqual(1, len(permissions))

        permission_codes = [p["code_name"] for p in permissions]
        self.assertIn(PermissionChoice.PORTAL_UPDATE_TRANSLATION, permission_codes)

    def test_get_profile_where_permissions_should_not_include_django_builtin_permissions(self):
        from django.contrib.auth.models import Permission

        # Arrange
        self.authenticate_user(self.user)
        # Give a Django built-in permission (e.g. "add_user")
        self.user.user_permissions.add(Permission.objects.get(codename="add_user"))

        # Act
        response = self.client.get("/cms-api/auth/profile/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        permissions = response.json()["permissions"]
        self.assertEqual(0, len(permissions))
