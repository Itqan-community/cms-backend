from datetime import timedelta

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.users.models import APIKey, User


@override_settings(ENABLE_API_KEY_AUTH=True)
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

    @override_settings(ENABLE_ANONYMOUS_TRAFFIC=True)
    def test_missing_api_key_falls_through_to_anonymous(self):
    # Act
        res = self.client.get("/recitations/")

    # Assert
        self.assertEqual(200, res.status_code, res.content)

    def test_cors_preflight_allows_x_api_key_header(self):
        # Act - emulate browser preflight OPTIONS request
        res = self.client.options(
            "/recitations/",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET",
                "access-control-request-headers": "x-api-key",
            },
        )

        # Assert
        self.assertEqual(200, res.status_code, res.content)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")
        allowed_headers = res.headers.get("access-control-allow-headers", "").lower()
        self.assertIn("x-api-key", allowed_headers)

    def test_cross_origin_request_with_valid_api_key(self):
        # Arrange
        _, raw_key = APIKey.objects.create_key(name="CORS Test Key", user=self.user)

        # Act - cross-origin GET request with x-api-key
        res = self.client.get(
            "/recitations/",
            headers={
                "origin": "http://localhost:3000",
                "x-api-key": raw_key,
            },
        )

        # Assert
        self.assertEqual(200, res.status_code, res.content)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")

    @override_settings(ENABLE_ANONYMOUS_TRAFFIC=False)
    def test_access_recitations_where_invalid_api_key_should_return_401(self):
        # Arrange — no valid key created

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": "invalid-key"})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("authentication_error", res.json()["error_name"])

    @override_settings(ENABLE_ANONYMOUS_TRAFFIC=False)
    def test_access_recitations_where_api_key_is_revoked_should_return_401(self):
        # Arrange
        api_key, raw_key = APIKey.objects.create_key(name="Revoked Key", user=self.user)
        api_key.revoked = True
        api_key.save()

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        self.assertEqual("authentication_error", res.json()["error_name"])

    @override_settings(ENABLE_ANONYMOUS_TRAFFIC=True)
    def test_access_recitations_where_api_key_is_expired_should_return_401_expired(self):
        # Arrange
        api_key, raw_key = APIKey.objects.create_key(name="Expired Key", user=self.user)
        api_key.expiry_date = timezone.now() - timedelta(days=1)
        api_key.save()

        # Act
        res = self.client.get("/recitations/", headers={"x-api-key": raw_key})

        # Assert
        self.assertEqual(401, res.status_code, res.content)
        body = res.json()
        self.assertEqual("authentication_error", body["error_name"])
        self.assertIn("expired", body["message"].lower())