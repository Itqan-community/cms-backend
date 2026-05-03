from django.conf import settings
from django.test import override_settings
from oauth2_provider.models import Application
import pytest

from apps.core.tests import BaseTestCase
from apps.users.models import User


@pytest.mark.skipif(not settings.ENABLE_OAUTH2, reason="OAuth2 disabled in settings")
@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
class OAuthApplicationTests(BaseTestCase):

    # --- Create ---

    def test_create_application_where_authenticated_user_should_return_client_id_and_secret(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/applications/", data={"name": "My Bot"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual("My Bot", data["name"])
        self.assertIn("id", data)
        self.assertIn("client_id", data)
        self.assertIn("client_secret", data)

    def test_create_application_where_anonymous_should_return_401(self):
        # Arrange
        self.authenticate_user(None)

        # Act
        response = self.client.post("/cms-api/applications/", data={"name": "My Bot"}, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)

    def test_create_application_where_name_duplicate_should_return_400_application_name_taken(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        Application.objects.create(
            user=user,
            name="My Bot",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.post("/cms-api/applications/", data={"name": "My Bot"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("application_name_taken", response.json()["error_name"])

    def test_create_application_where_name_is_whitespace_should_return_400_invalid_application_name(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/applications/", data={"name": "   "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_application_name", response.json()["error_name"])

    def test_create_application_where_name_too_long_should_return_400_invalid_application_name(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/applications/", data={"name": "a" * 121}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_application_name", response.json()["error_name"])

    def test_create_application_where_grant_type_in_body_should_be_ignored_and_client_credentials_always_applied(self):
        # Arrange — authorization_grant_type is not a recognized field; any value passed is ignored
        # and client-credentials is always enforced server-side
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post(
            "/cms-api/applications/",
            data={"name": "My Bot", "authorization_grant_type": "password"},
            format="json",
        )

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        app = Application.objects.get(user=user, name="My Bot")
        self.assertEqual(Application.GRANT_CLIENT_CREDENTIALS, app.authorization_grant_type)

    # --- List ---

    def test_list_applications_where_user_has_apps_should_not_include_client_secret(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        Application.objects.create(
            user=user,
            name="App 1",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.get("/cms-api/applications/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        self.assertEqual(1, len(items))
        self.assertNotIn("client_secret", items[0])

    def test_list_applications_where_other_users_apps_exist_should_only_return_own(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        Application.objects.create(
            user=user,
            name="Mine",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        Application.objects.create(
            user=other,
            name="Theirs",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.get("/cms-api/applications/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        self.assertEqual(1, len(items))
        self.assertEqual("Mine", items[0]["name"])

    # --- Retrieve ---

    def test_retrieve_application_where_owned_should_not_include_client_secret(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=user,
            name="App 1",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.get(f"/cms-api/applications/{app.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertNotIn("client_secret", response.json())

    def test_retrieve_application_where_owned_by_other_user_should_return_404_application_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=other,
            name="Theirs",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.get(f"/cms-api/applications/{app.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("application_not_found", response.json()["error_name"])

    # --- Rename ---

    def test_rename_application_where_valid_name_should_return_200(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=user,
            name="Old Name",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.patch(f"/cms-api/applications/{app.id}/", data={"name": "New Name"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("New Name", response.json()["name"])
        app.refresh_from_db()
        self.assertEqual("New Name", app.name)

    def test_rename_application_where_duplicate_name_should_return_400_application_name_taken(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        Application.objects.create(
            user=user,
            name="Existing",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )
        app = Application.objects.create(
            user=user,
            name="My Bot",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.patch(f"/cms-api/applications/{app.id}/", data={"name": "Existing"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("application_name_taken", response.json()["error_name"])

    def test_rename_application_where_not_owned_should_return_404_application_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=other,
            name="Theirs",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.patch(f"/cms-api/applications/{app.id}/", data={"name": "Hijack"}, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("application_not_found", response.json()["error_name"])

    # --- Delete ---

    def test_delete_application_where_owned_should_return_204(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=user,
            name="App 1",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.delete(f"/cms-api/applications/{app.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(Application.objects.filter(id=app.id).exists())

    def test_delete_application_where_not_owned_should_return_404_application_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        app = Application.objects.create(
            user=other,
            name="Theirs",
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
        )

        # Act
        response = self.client.delete(f"/cms-api/applications/{app.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("application_not_found", response.json()["error_name"])
