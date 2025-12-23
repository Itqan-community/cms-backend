from django.utils.crypto import get_random_string

from apps.core.tests import BaseTestCase
from apps.users.models import User


class PublicRegistrationTestCase(BaseTestCase):
    """Tests for public user registration endpoint"""

    def test_register_user_where_valid_data_should_return_200_with_tokens(self):
        """Test successful user registration via public endpoint"""
        # Arrange
        email = f"public_{get_random_string(8).lower()}@example.com"
        password = get_random_string(16)
        data = {
            "email": email,
            "password": password,
            "name": "Public Dev User",
            "job_title": "Software Engineer",
        }

        # Act - Public endpoint is at /register/
        response = self.client.post("/register/", data=data, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        response_data = response.json()

        # Check response structure
        self.assertIn("access", response_data)
        self.assertIn("refresh", response_data)
        self.assertIn("user", response_data)

        # Check user data
        user_data = response_data["user"]
        self.assertEqual(email, user_data["email"])
        self.assertEqual(data["name"], user_data["name"])
        self.assertTrue(user_data["is_active"])
        self.assertTrue(user_data["created"])

        # Verify user was created in database
        self.assertTrue(User.objects.filter(email=email).exists())
        user = User.objects.get(email=email)
        self.assertEqual(user.developer_profile.job_title, "Software Engineer")

    def test_register_user_where_duplicate_email_should_return_400(self):
        """Test registration with duplicate email via public endpoint"""
        # Arrange
        email = "duplicate@example.com"
        User.objects.create_user(email=email, password="password")
        data = {
            "email": email,
            "password": "newpassword",
            "name": "Another User",
        }

        # Act
        response = self.client.post("/register/", data=data, format="json")

        # Assert
        self.assertEqual(400, response.status_code)
        response_data = response.json()
        self.assertEqual("email_already_exists", response_data["error_name"])
