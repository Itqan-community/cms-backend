from datetime import timedelta

from django.test import override_settings
from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.users.models import APIKey, User


# PublicAuth reads these flags on every request, so @override_settings takes effect.
@override_settings(ENABLE_API_KEY_AUTH=True, ENABLE_ANONYMOUS_TRAFFIC=True)
class ApiKeyWorkflowTestCase(BaseTestCase):
    """
    End-to-End test for the API key workflow:
    Create API Key -> Access Protected API using X-API-Key header
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = baker.make(User)

    def test_full_api_key_workflow_success(self):
        # Arrange
        _, raw_key = APIKey.objects.create_key(name="E2E Test Key", user=self.user)

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(200, res.status_code, res.content)

    def test_access_recitations_where_no_api_key_should_return_200_as_anonymous(self):
        # Arrange: anonymous traffic is on and no key is sent

        # Act
        res = self.client.get("/recitations/")

        # Assert
        self.assertEqual(200, res.status_code, res.content)

    # A key that is sent but unusable is rejected even though anonymous traffic is allowed:
    # it must not quietly fall back to the anonymous budget.
    def test_access_recitations_where_invalid_api_key_should_return_401_invalid_api_key(self):
        # Arrange: no key with this prefix exists

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": "bogus.key"})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("invalid_api_key", res.json()["error_name"])

    def test_access_recitations_where_api_key_secret_is_wrong_should_return_401_invalid_api_key(self):
        # Arrange: a real prefix with the wrong secret
        api_key, _ = APIKey.objects.create_key(name="Real Key", user=self.user)

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": f"{api_key.prefix}.wrong-secret"})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("invalid_api_key", res.json()["error_name"])

    def test_access_recitations_where_api_key_is_revoked_should_return_401_invalid_api_key(self):
        # Arrange
        api_key, raw_key = APIKey.objects.create_key(name="Revoked Key", user=self.user)
        api_key.revoked = True
        api_key.save()

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("invalid_api_key", res.json()["error_name"])

    def test_access_recitations_where_api_key_is_expired_should_return_401_invalid_api_key(self):
        # Arrange
        api_key, raw_key = APIKey.objects.create_key(name="Expired Key", user=self.user)
        api_key.expiry_date = timezone.now() - timedelta(days=1)
        api_key.save()

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        body = res.json()
        self.assertEqual("invalid_api_key", body["error_name"])
        self.assertIn("expired", body["message"].lower())

    def test_access_tenant_recitations_where_invalid_api_key_should_return_401_invalid_api_key(self):
        # Arrange: the tenant API's optional auth tries API keys too

        # Act
        res = self.client.get("/tenant/recitations/", headers={"x-api-key": "bogus.key"})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("invalid_api_key", res.json()["error_name"])
