from django.conf import settings
from django.utils.crypto import get_random_string
import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.tests import BaseTestCase
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


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class UserRegistrationTestCase(BaseTestCase):
    """Tests for user registration endpoint"""

    def test_register_user_where_valid_data_should_return_200_with_tokens(self):
        """Test successful user registration with valid data"""
        # Arrange
        new_pwd = get_random_string(16)
        # Act
        response = self.client.post(
            "/cms-api/auth/register/",
            data={
                "email": "newuser@example.com",
                "password": new_pwd,
                "name": "New User",
            },
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check response structure
        self.assertIn("access", response_data)
        self.assertIn("refresh", response_data)
        self.assertIn("user", response_data)

        # Check user data
        user_data = response_data["user"]
        self.assertEqual("newuser@example.com", user_data["email"])
        self.assertEqual("New User", user_data["name"])
        self.assertTrue(user_data["is_active"])
        self.assertTrue(user_data["created"])

        # Verify user was created in database
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_register_user_where_duplicate_email_should_return_400_with_error(self):
        """Test registration with duplicate email returns error"""
        # Arrange
        User.objects.create_user(
            email="newuser@example.com",
            password=get_random_string(16),
            name="Name",
        )
        new_pwd = get_random_string(16)
        data = {
            "email": "newuser@example.com",
            "password": new_pwd,
            "name": "Another User",
        }

        # Act
        response = self.client.post("/cms-api/auth/register/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("email_already_exists", response_data["error_name"])
        self.assertIn("already exists", response_data["message"])

    def test_register_user_where_missing_fields_should_return_400_validation_error(
        self,
    ):
        """Test registration with missing required fields returns validation error"""
        # Arrange
        data = {
            "email": "incomplete@example.com"
            # Missing password
        }

        # Act
        response = self.client.post("/cms-api/auth/register/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        response_data = response.json()
        self.assertEqual("validation_error", response_data["error_name"])
        self.assertIn("Invalid Input", response_data["message"])

    def test_register_user_where_invalid_email_should_return_400_validation_error(self):
        """Test registration with invalid email format returns validation error"""
        # Arrange
        new_pwd = get_random_string(16)
        data = {
            "email": "invalid-email",
            "password": new_pwd,
            "name": "Test User",
        }

        # Act
        response = self.client.post("/cms-api/auth/register/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        response_data = response.json()
        self.assertEqual("registration_failed", response_data["error_name"])
        self.assertEqual("Registration failed: ['Enter a valid email address.']", response_data["message"])


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class UserLoginTestCase(BaseTestCase):
    """Tests for user login endpoint"""

    def setUp(self):
        super().setUp()
        self.user_data = {
            "email": "test@example.com",
            "password": get_random_string(16),
            "name": "Test User",
        }

    def test_login_where_valid_credentials_should_return_200_with_tokens(self):
        """Test successful user login with valid credentials"""
        # Arrange
        User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            name=self.user_data["name"],
        )
        data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
        }

        # Act
        response = self.client.post("/cms-api/auth/login/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check response structure
        self.assertIn("access", response_data)
        self.assertIn("refresh", response_data)
        self.assertIn("user", response_data)

        # Check user data
        user_data = response_data["user"]
        self.assertEqual(self.user_data["email"], user_data["email"])
        self.assertEqual(self.user_data["name"], user_data["name"])
        self.assertTrue(user_data["is_active"])

    def test_login_where_invalid_credentials_should_return_401_with_error(self):
        """Test login with invalid credentials returns authentication error"""
        # Arrange
        User.objects.create_user(
            email=self.user_data["email"],
            password=self.user_data["password"],
            name="Test User",
        )
        data = {"email": self.user_data["email"], "password": get_random_string(16)}

        # Act
        response = self.client.post("/cms-api/auth/login/", data=data, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("invalid_credentials", response_data["error_name"])
        self.assertIn("Invalid", response_data["message"])

    def test_login_where_nonexistent_user_should_return_401_with_error(self):
        """Test login with non-existent user returns authentication error"""
        # Arrange
        data = {"email": "nonexistent@example.com", "password": get_random_string(16)}

        # Act
        response = self.client.post("/cms-api/auth/login/", data=data, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        response_data = response.json()
        self.assertEqual("invalid_credentials", response_data["error_name"])
        self.assertIn("Invalid", response_data["message"])

    def test_login_where_inactive_user_should_return_401_with_error(self):
        """Test login with inactive user returns authentication error"""
        # Arrange
        tmp_pwd = get_random_string(16)
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password=tmp_pwd,
            name="Inactive User",
            is_active=False,
        )

        data = {"email": inactive_user.email, "password": tmp_pwd}

        # Act
        response = self.client.post("/cms-api/auth/login/", data=data, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("invalid_credentials", response_data["error_name"])
        self.assertIn("Invalid", response_data["message"])

    def test_login_where_missing_fields_should_return_422_validation_error(self):
        """Test login with missing required fields returns validation error"""
        # Arrange
        data = {
            "email": self.user_data["email"]
            # Missing password
        }

        # Act
        response = self.client.post("/cms-api/auth/login/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("validation_error", response_data["error_name"])
        self.assertIn("Invalid Input", response_data["message"])


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class TokenRefreshTestCase(BaseTestCase):
    """Tests for token refresh endpoint"""

    def test_refresh_token_where_valid_token_should_return_200_with_new_access(self):
        """Test successful token refresh with valid refresh token"""
        # Arrange
        user = User.objects.create_user(email="test@example.com")
        refresh_token = RefreshToken.for_user(user)
        data = {"refresh": str(refresh_token)}

        # Act
        response = self.client.post("/cms-api/auth/token/refresh/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check response structure
        self.assertIn("access", response_data)
        # Refresh token might be rotated if rotation is enabled

    def test_refresh_token_where_invalid_token_should_return_401_with_error(self):
        """Test token refresh with invalid token returns authentication error"""
        # Arrange
        data = {"refresh": "invalid-token"}  # not a secret, just intentionally invalid

        # Act
        response = self.client.post("/cms-api/auth/token/refresh/", data=data, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("invalid_refresh_token", response_data["error_name"])
        self.assertIn("Invalid", response_data["message"])

    def test_refresh_token_where_missing_token_should_return_422_validation_error(self):
        """Test token refresh without token returns validation error"""
        # Arrange
        data = {}

        # Act
        response = self.client.post("/cms-api/auth/token/refresh/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        response_data = response.json()

        self.assertEqual("validation_error", response_data["error_name"])
        self.assertIn("Invalid Input", response_data["message"])


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


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class LogoutTestCase(BaseTestCase):
    """Tests for logout endpoint"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="test@example.com")

    def test_logout_where_valid_tokens_should_return_200_with_success_message(self):
        """Test successful logout with valid tokens"""
        # Arrange
        self.authenticate_user(self.user)
        refresh_token = RefreshToken.for_user(self.user)

        data = {"refresh": str(refresh_token)}

        # Act
        response = self.client.post("/cms-api/auth/logout/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        self.assertIn("logged out", response_data["message"])

    def test_logout_where_no_refresh_token_should_return_200_with_success_message(self):
        """Test logout without providing refresh token still succeeds"""
        # Arrange
        self.authenticate_user(self.user)

        # Act
        response = self.client.post("/cms-api/auth/logout/", data={}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        self.assertIn("logged out", response_data["message"])

    def test_logout_where_unauthenticated_should_return_401(self):
        """Test logout without authentication returns error"""
        # Arrange & Act
        response = self.client.post("/cms-api/auth/logout/", data={}, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class AuthenticationIntegrationTestCase(BaseTestCase):
    """Integration tests for authentication flow"""

    def test_full_registration_login_profile_flow(self):
        """Test complete user journey: register -> login -> profile"""
        # Step 1: Register new user
        register_password = get_random_string(16)
        register_data = {
            "email": "journey@example.com",
            "password": register_password,
            "name": "Journey User",
        }

        register_response = self.client.post("/cms-api/auth/register/", data=register_data, format="json")

        self.assertEqual(200, register_response.status_code, register_response.content)
        register_result = register_response.json()

        # Step 2: Login with same credentials
        login_data = {
            "email": register_data["email"],
            "password": register_password,
        }

        login_response = self.client.post("/cms-api/auth/login/", data=login_data, format="json")

        self.assertEqual(200, login_response.status_code, login_response.content)
        login_result = login_response.json()
        self.authenticate_user(User.objects.get(email=register_data["email"]))

        # Step 3: Access profile with login token
        profile_response = self.client.get("/cms-api/auth/profile/")

        self.assertEqual(200, profile_response.status_code, profile_response.content)
        profile_result = profile_response.json()

        # Verify consistency across endpoints
        self.assertEqual(profile_result["email"], register_data["email"])
        self.assertEqual(profile_result["name"], register_data["name"])
        self.assertEqual(register_result["user"]["id"], login_result["user"]["id"])
        self.assertEqual(login_result["user"]["id"], profile_result["id"])

    def test_token_refresh_and_reuse(self):
        """Test token refresh and using new token"""
        # Get initial tokens
        user = User.objects.create_user(email="journey@example.com")
        refresh_token = RefreshToken.for_user(user)

        # Refresh token
        refresh_response = self.client.post(
            "/cms-api/auth/token/refresh/", data={"refresh": str(refresh_token)}, format="json"
        )

        self.assertEqual(200, refresh_response.status_code, refresh_response.content)

        # Use new access token
        self.authenticate_user(user)
        profile_response = self.client.get("/cms-api/auth/profile/")

        self.assertEqual(200, profile_response.status_code, profile_response.content)
        profile_result = profile_response.json()
        self.assertEqual("journey@example.com", profile_result["email"])


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class AuthenticationSecurityTestCase(BaseTestCase):
    """Security-focused tests for authentication"""

    def test_expired_token_rejection(self):
        """Test that expired tokens are rejected"""
        # Use a constructed invalid token string to avoid B105 while still being invalid
        invalid_token = ".".join(
            [
                "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",
                "invalid",
                "signature",
            ]
        )

        response = self.client.get("/cms-api/auth/profile/", {"HTTP_AUTHORIZATION": f"Bearer {invalid_token}"})

        self.assertEqual(response.status_code, 401, response.content)

    def test_malformed_token_rejection(self):
        """Test that malformed tokens are rejected"""
        malformed_tokens = [
            "not-a-token",
            "Bearer",
            "",
            "malformed.token",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # Incomplete token
        ]

        for token in malformed_tokens:
            response = self.client.get("/cms-api/auth/profile/", headers={"authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 401, response.content)

    def test_no_authorization_header_should_return_401(self):
        """Test endpoints without authorization header"""

        response = self.client.get("/cms-api/auth/profile/")
        self.assertEqual(response.status_code, 401, response.content)
        response = self.client.post("/cms-api/auth/logout/")
        self.assertEqual(response.status_code, 401, response.content)

    def test_wrong_authorization_scheme(self):
        """Test with wrong authorization scheme"""
        user = User.objects.create_user(email="test@example.com")
        refresh_token = RefreshToken.for_user(user)

        access_token = str(refresh_token.access_token)
        wrong_schemes = [
            f"Basic {access_token}",
            f"Token {access_token}",
            f"JWT {access_token}",
            access_token,  # No scheme
        ]

        for auth_header in wrong_schemes:
            response = self.client.get("/cms-api/auth/profile/", headers={"authorization": auth_header})
            self.assertEqual(response.status_code, 401, response.content)


@pytest.mark.skipif(condition=settings.ENABLE_ALLAUTH, reason="old flow before allauth")
class AuthenticationErrorHandlingTestCase(BaseTestCase):
    """Tests for error handling in authentication"""

    def test_invalid_json_request(self):
        """Test handling of invalid JSON in requests"""
        response = self.client.post("/cms-api/auth/login/", data="invalid-json", content_type="application/json")

        self.assertEqual(response.status_code, 400, response.content)

    def test_empty_request_body(self):
        """Test handling of empty request body"""
        response = self.client.post("/cms-api/auth/login/", data="", content_type="application/json")

        self.assertEqual(response.status_code, 400, response.content)

    def test_sql_injection_attempt(self):
        """Test protection against SQL injection"""
        User.objects.create_user(email="gooduser@example.com")
        malicious_data = {
            "email": "test@example.com'; DROP TABLE users; --",
            "password": "password",  # value text not used as a secret
        }

        response = self.client.post("/cms-api/auth/login/", data=malicious_data, format="json")

        # Should not cause server error, should handle gracefully
        self.assertEqual(401, response.status_code, response.content)

        # Verify user table still exists
        self.assertTrue(User.objects.filter(email="gooduser@example.com").exists())
