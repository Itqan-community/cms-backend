from oauth2_provider.models import Application
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.tests import BaseTestCase
from apps.users.models import User


class OAuth2ApplicationTests(BaseTestCase):
    """Test suite for OAuth2 Application CRUD endpoints"""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="appuser@example.com", password="password123", name="App User")
        # Get JWT token for Ninja authentication
        refresh = RefreshToken.for_user(self.user)
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {refresh.access_token}"}

    def test_create_application_where_valid_data_should_return_200(self):
        """Test creating an application"""
        data = {
            "name": "New App",
            "client_type": "confidential",
            "authorization_grant_type": "password",
            "redirect_uris": "http://localhost/cb",
        }
        response = self.client.post("/cms-api/applications/", data=data, format="json", **self.auth_headers)
        self.assertEqual(200, response.status_code, response.content)
        res_data = response.json()
        self.assertEqual("New App", res_data["name"])
        self.assertIn("client_id", res_data)
        self.assertIn("client_secret", res_data)

    def test_list_applications_where_user_has_apps_should_return_list(self):
        """Test listing applications"""
        Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        response = self.client.get("/cms-api/applications/", **self.auth_headers)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(response.json()))

    def test_get_application_where_exists_should_return_app(self):
        """Test getting a specific application"""
        app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        response = self.client.get(f"/cms-api/applications/{app.id}/", **self.auth_headers)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("App 1", response.json()["name"])

    def test_update_application_where_exists_should_modify_app(self):
        """Test updating an application"""
        app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        data = {"name": "Updated App"}
        response = self.client.put(f"/cms-api/applications/{app.id}/", data=data, format="json", **self.auth_headers)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("Updated App", response.json()["name"])
        app.refresh_from_db()
        self.assertEqual("Updated App", app.name)

    def test_delete_application_where_exists_should_remove_app(self):
        """Test deleting an application"""
        app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        response = self.client.delete(f"/cms-api/applications/{app.id}/", **self.auth_headers)
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Application.objects.filter(id=app.id).exists())
