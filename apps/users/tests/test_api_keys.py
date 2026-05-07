from django.test import override_settings

from apps.core.tests import BaseTestCase
from apps.users.models import User, UserAPIKey


@override_settings(ENABLE_API_KEY_AUTH=True)
class ApiKeyTests(BaseTestCase):

    # --- Create ---

    def test_create_api_key_where_authenticated_user_should_return_raw_key_once(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "My Key"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        data = response.json()
        self.assertEqual("My Key", data["name"])
        self.assertIn("id", data)
        self.assertIn("key", data)
        self.assertFalse(data["revoked"])

    def test_create_api_key_where_anonymous_should_return_401(self):
        # Arrange — unauthenticated

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "My Key"}, format="json")

        # Assert
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual("authentication_error", response.json()["error_name"])

    def test_create_api_key_where_name_is_duplicate_should_return_400_api_key_name_taken(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        UserAPIKey.objects.create_key(name="My Key", user=user)

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "My Key"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("api_key_name_taken", response.json()["error_name"])

    def test_create_api_key_where_name_is_whitespace_should_return_400_invalid_api_key_name(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "   "}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_api_key_name", response.json()["error_name"])

    def test_create_api_key_where_name_too_long_should_return_400_invalid_api_key_name(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "a" * 51}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_api_key_name", response.json()["error_name"])

    def test_create_api_key_where_duplicate_name_on_different_user_should_return_200(self):
        # Arrange — same name is OK for a different user
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        UserAPIKey.objects.create_key(name="Shared Name", user=other)
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)

        # Act
        response = self.client.post("/cms-api/api-keys/", data={"name": "Shared Name"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)

    # --- List ---

    def test_list_api_keys_where_user_has_keys_should_not_include_raw_key(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        UserAPIKey.objects.create_key(name="Key 1", user=user)

        # Act
        response = self.client.get("/cms-api/api-keys/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        self.assertEqual(1, len(items))
        self.assertNotIn("key", items[0])

    def test_list_api_keys_where_other_users_keys_exist_should_only_return_own(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        UserAPIKey.objects.create_key(name="Mine", user=user)
        UserAPIKey.objects.create_key(name="Theirs", user=other)

        # Act
        response = self.client.get("/cms-api/api-keys/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        self.assertEqual(1, len(items))
        self.assertEqual("Mine", items[0]["name"])

    def test_list_api_keys_where_revoked_key_exists_should_include_it(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="Old Key", user=user)
        api_key.revoked = True
        api_key.save()

        # Act
        response = self.client.get("/cms-api/api-keys/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        items = response.json()
        self.assertEqual(1, len(items))
        self.assertTrue(items[0]["revoked"])

    # --- Retrieve ---

    def test_get_api_key_where_owned_should_return_200(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="My Key", user=user)

        # Act
        response = self.client.get(f"/cms-api/api-keys/{api_key.id}/")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("My Key", response.json()["name"])
        self.assertNotIn("key", response.json())

    def test_get_api_key_where_owned_by_other_user_should_return_404_api_key_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="Theirs", user=other)

        # Act
        response = self.client.get(f"/cms-api/api-keys/{api_key.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("api_key_not_found", response.json()["error_name"])

    # --- Update ---

    def test_update_api_key_where_valid_name_should_return_200(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="Old Name", user=user)

        # Act
        response = self.client.patch(f"/cms-api/api-keys/{api_key.id}/", data={"name": "New Name"}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual("New Name", response.json()["name"])
        api_key.refresh_from_db()
        self.assertEqual("New Name", api_key.name)

    def test_update_api_key_where_revoked_true_should_return_200(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="My Key", user=user)

        # Act
        response = self.client.patch(f"/cms-api/api-keys/{api_key.id}/", data={"revoked": True}, format="json")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        self.assertTrue(response.json()["revoked"])
        api_key.refresh_from_db()
        self.assertTrue(api_key.revoked)

    def test_update_api_key_where_revoked_false_on_revoked_key_should_return_400_api_key_revoke_irreversible(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="My Key", user=user)
        api_key.revoked = True
        api_key.save()

        # Act
        response = self.client.patch(f"/cms-api/api-keys/{api_key.id}/", data={"revoked": False}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("api_key_revoke_irreversible", response.json()["error_name"])

    def test_update_api_key_where_duplicate_name_should_return_400_api_key_name_taken(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        UserAPIKey.objects.create_key(name="Existing", user=user)
        api_key, _ = UserAPIKey.objects.create_key(name="My Key", user=user)

        # Act
        response = self.client.patch(f"/cms-api/api-keys/{api_key.id}/", data={"name": "Existing"}, format="json")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("api_key_name_taken", response.json()["error_name"])

    def test_update_api_key_where_not_owned_should_return_404_api_key_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="Theirs", user=other)

        # Act
        response = self.client.patch(f"/cms-api/api-keys/{api_key.id}/", data={"name": "Hijack"}, format="json")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("api_key_not_found", response.json()["error_name"])

    # --- Delete ---

    def test_delete_api_key_where_owned_should_return_204(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="My Key", user=user)

        # Act
        response = self.client.delete(f"/cms-api/api-keys/{api_key.id}/")

        # Assert
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(UserAPIKey.objects.filter(id=api_key.id).exists())

    def test_delete_api_key_where_not_owned_should_return_404_api_key_not_found(self):
        # Arrange
        user = User.objects.create_user(email="user@example.com", password="pass123", name="User")
        other = User.objects.create_user(email="other@example.com", password="pass123", name="Other")
        self.authenticate_user(user)
        api_key, _ = UserAPIKey.objects.create_key(name="Theirs", user=other)

        # Act
        response = self.client.delete(f"/cms-api/api-keys/{api_key.id}/")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("api_key_not_found", response.json()["error_name"])
