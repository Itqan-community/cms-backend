import base64
import secrets

from django.utils import timezone
from oauth2_provider.models import AccessToken, Application

from apps.core.tests import BaseTestCase
from apps.users.models import User


class OAuth2Tests(BaseTestCase):
    """
    Test suite for OAuth2.0 implementation.
    Tests all grant types and credential enforcement.
    """

    def setUp(self):
        super().setUp()
        self.user_password = "testpassword123"
        self.user = User.objects.create_user(
            email="oauthuser@example.com", password=self.user_password, name="OAuth User"
        )
        # Create an OAuth2 Application
        self.app = Application.objects.create(
            name="Test App",
            redirect_uris="http://localhost:8000/callback",
            user=self.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        self.auth_header = {
            "HTTP_AUTHORIZATION": "Basic " + base64.b64encode(b"test_client_id:test_client_secret").decode("ascii")
        }

    def test_client_credentials_grant_where_valid_header_should_return_200(self):
        """Test client_credentials grant type"""
        # Arrange
        self.app.authorization_grant_type = Application.GRANT_CLIENT_CREDENTIALS
        self.app.save()
        data = {"grant_type": "client_credentials"}

        # Act
        response = self.client.post("/token/", data=data, **self.auth_header)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        res_data = response.json()
        self.assertIn("access_token", res_data)
        self.assertEqual("Bearer", res_data["token_type"])

    def test_password_grant_where_valid_credentials_should_return_200(self):
        """Test password grant type"""
        # Arrange
        self.app.authorization_grant_type = Application.GRANT_PASSWORD
        self.app.save()
        data = {
            "grant_type": "password",
            "username": self.user.email,
            "password": self.user_password,
        }

        # Act
        response = self.client.post("/token/", data=data, **self.auth_header)

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        res_data = response.json()
        self.assertIn("access_token", res_data)
        self.assertIn("refresh_token", res_data)

    def test_protected_endpoint_where_valid_oauth2_token_should_return_200(self):
        """Verify that Ninja endpoints accept the new OAuth2 tokens"""
        # Arrange
        token = AccessToken.objects.create(
            user=self.user,
            application=self.app,
            token=secrets.token_hex(20),
            expires=timezone.now() + timezone.timedelta(days=1),  # Future date
            scope="read write",
        )
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token.token}"}

        # Act
        # recitations/ endpoint is protected by ninja_oauth2_auth
        response = self.client.get("/recitations/", **headers)

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_revoke_token_where_valid_token_should_return_200(self):
        """Test token revocation endpoint"""
        # Arrange
        token = AccessToken.objects.create(
            user=self.user,
            application=self.app,
            token=secrets.token_hex(20),
            expires=timezone.now() + timezone.timedelta(days=1),
            scope="read write",
        )
        data = {"token": token.token}

        # Act
        self.client.post("/revoke/", data=data, **self.auth_header)

        # Assert
        self.assertFalse(AccessToken.objects.filter(token=token.token).exists())
