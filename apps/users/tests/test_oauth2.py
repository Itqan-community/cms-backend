import base64
import datetime
import secrets

from django.conf import settings
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application
import pytest

from apps.core.tests import BaseTestCase
from apps.users.models import User

_CLIENT_ID = "test_client_id"
_CLIENT_SECRET = "test_client_secret"


def _basic_auth(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET) -> dict:
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return {"HTTP_AUTHORIZATION": f"Basic {encoded}"}


@pytest.mark.skipif(not settings.ENABLE_OAUTH2, reason="OAuth2 disabled in settings")
class OAuth2Tests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="oauthuser@example.com", password="pass123", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="Test App",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
        )

    # --- Token endpoint ---

    def test_token_where_valid_client_credentials_should_return_access_token(self):
        # Arrange
        data = {"grant_type": "client_credentials"}

        # Act
        response = self.client.post("/token/", data=data, **_basic_auth())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        res_data = response.json()
        self.assertIn("access_token", res_data)
        self.assertEqual("Bearer", res_data["token_type"])
        self.assertNotIn("refresh_token", res_data)

    def test_token_where_invalid_client_secret_should_return_401_invalid_client(self):
        # Arrange
        data = {"grant_type": "client_credentials"}

        # Act
        response = self.client.post("/token/", data=data, **_basic_auth(client_secret="wrong_secret"))

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("invalid_client", response.json()["error"])

    def test_token_where_any_grant_type_is_overridden_to_client_credentials(self):
        # Arrange — grant_type is always forced to client_credentials server-side
        data = {"grant_type": "password", "username": "oauthuser@example.com", "password": "pass123"}

        # Act
        response = self.client.post("/token/", data=data, **_basic_auth())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertIn("access_token", response.json())

    def test_token_where_no_authorization_header_should_return_401(self):
        # Arrange
        data = {"grant_type": "client_credentials"}

        # Act
        response = self.client.post("/token/", data=data)

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    # --- Protected developers_api endpoint ---

    def test_protected_endpoint_where_valid_token_should_return_200(self):
        # Arrange
        token = AccessToken.objects.create(
            user=self.user,
            application=self.app,
            token=secrets.token_hex(20),
            expires=timezone.now() + datetime.timedelta(days=1),
            scope="read",
        )

        # Act
        response = self.client.get("/recitations/", headers={"authorization": f"Bearer {token.token}"})

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    def test_protected_endpoint_where_expired_token_should_return_401(self):
        # Arrange
        token = AccessToken.objects.create(
            user=self.user,
            application=self.app,
            token=secrets.token_hex(20),
            expires=timezone.now() - datetime.timedelta(seconds=1),
            scope="read",
        )

        # Act
        response = self.client.get("/recitations/", headers={"authorization": f"Bearer {token.token}"})

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    # --- Revoke endpoint ---

    def test_revoke_token_where_valid_token_should_delete_it(self):
        # Arrange
        token = AccessToken.objects.create(
            user=self.user,
            application=self.app,
            token=secrets.token_hex(20),
            expires=timezone.now() + datetime.timedelta(days=1),
            scope="read",
        )
        data = {"token": token.token}

        # Act
        response = self.client.post("/revoke/", data=data, **_basic_auth())

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertFalse(AccessToken.objects.filter(token=token.token).exists())
