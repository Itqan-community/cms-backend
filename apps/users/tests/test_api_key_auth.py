from django.test import override_settings
from ninja_keys.models import APIKey

from apps.core.tests import BaseTestCase


@override_settings(ENABLE_API_KEY_AUTH=True, ENABLE_OAUTH2=True)
class ApiKeyWorkflowTestCase(BaseTestCase):
    """
    End-to-End test for the API key workflow:
    Create API Key -> Access Protected API using X-API-Key header
    """

    def test_full_api_key_workflow_success(self):
        # Arrange
        _, raw_key = APIKey.objects.create_key(name="E2E Test Key")

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(200, res.status_code, res.content)

    def test_access_recitations_where_invalid_api_key_should_return_401(self):
        # Arrange — no valid key created

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": "invalid-key"})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("authentication_error", res.json()["error_name"])

    def test_access_recitations_where_no_api_key_provided_should_return_401(self):
        # Arrange — no key provided

        # Act
        res = self.client.get("/recitations/")

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("authentication_error", res.json()["error_name"])

    def test_access_recitations_where_api_key_is_revoked_should_return_401(self):
        # Arrange
        api_key, raw_key = APIKey.objects.create_key(name="Revoked Key")
        api_key.revoked = True
        api_key.save()

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("authentication_error", res.json()["error_name"])
