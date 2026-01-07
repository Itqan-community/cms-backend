import base64

from django.conf import settings
from django.utils.crypto import get_random_string
import pytest

from apps.core.tests import BaseTestCase


@pytest.mark.skipif(condition=not settings.ENABLE_ALLAUTH, reason="related only to allauth headless flow")
class OAuth2WorkflowTestCase(BaseTestCase):
    """
    End-to-End test for the OAuth2 workflow:
    Register -> Create Application -> Get OAuth2 Token -> Access Protected API
    """

    def test_full_onboarding_workflow_success(self):
        # --- STEP 1: Register User (Public Endpoint) ---
        email = f"workflow_{get_random_string(8).lower()}@example.com"
        password = get_random_string(16)
        reg_data = {
            "email": email,
            "password": password,
        }

        reg_res = self.client.post("/cms-api/auth/app/v1/auth/signup", data=reg_data, format="json")
        self.assertEqual(200, reg_res.status_code, reg_res.content)

        # Verify login works to get JWT access token
        client2 = self.client_class()
        login_res = client2.post("/cms-api/auth/app/v1/auth/login", data=reg_data, format="json")
        self.assertEqual(200, login_res.status_code, login_res.content)

        refresh_token = login_res.json()["meta"]["refresh_token"]
        access_token = login_res.json()["meta"]["access_token"]

        refresh_res = client2.post(
            "/cms-api/auth/app/v1/tokens/refresh", data={"refresh_token": refresh_token}, format="json"
        )
        self.assertEqual(200, refresh_res.status_code, refresh_res.content)
        new_access_token = refresh_res.json()["data"]["access_token"]
        self.assertNotEqual(new_access_token, access_token)

        # --- STEP 2: Create OAuth2 Application (Authenticated via JWT) ---
        app_data = {
            "name": "E2E Postman App",
            "client_type": "confidential",
            "authorization_grant_type": "password",
        }
        headers = {"HTTP_AUTHORIZATION": f"Bearer {new_access_token}"}

        app_res = self.client.post("/cms-api/applications/", data=app_data, format="json", **headers)
        self.assertEqual(200, app_res.status_code, app_res.content)
        app_json = app_res.json()

        client_id = app_json["client_id"]
        client_secret = app_json["client_secret"]
        self.assertEqual("E2E Postman App", app_json["name"])
        self.assertEqual("password", app_json["authorization_grant_type"])

        # --- STEP 3: Retrieve OAuth2 Token (Client Credentials Grant) ---
        # Encode for Basic Auth header
        auth_str = f"{client_id}:{client_secret}"
        auth_bytes = auth_str.encode("ascii")
        auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        token_headers = {"HTTP_AUTHORIZATION": f"Basic {auth_b64}"}
        token_data = {"grant_type": "password", "username": email, "password": password}

        # Public token endpoint at /token/
        token_res = self.client.post("/token/", data=token_data, **token_headers)
        self.assertEqual(200, token_res.status_code, token_res.content)
        token_json = token_res.json()
        oauth2_access_token = token_json["access_token"]
        self.assertEqual("Bearer", token_json["token_type"])

        # --- STEP 4: Access Protected API (Authenticated via OAuth2 Token) ---
        final_headers = {"HTTP_AUTHORIZATION": f"Bearer {oauth2_access_token}"}
        res = self.client.get("/recitations/", **final_headers)
        self.assertEqual(200, res.status_code, res.content)
