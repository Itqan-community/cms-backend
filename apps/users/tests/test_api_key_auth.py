from datetime import timedelta
from unittest import skipUnless

from django.conf import settings
from django.test import override_settings
from django.utils import timezone
from model_bakery import baker

from apps.core.tests.base import BaseTestCase
from apps.users.models import APIKey, User


# Auth config (auth.py public_auth) is built at import time from settings, so
# @override_settings cannot make OAuth2 required at runtime. These tests are only
# meaningful when OAuth2 is actually enabled at process start; otherwise the public
# auth falls back to AnonymousUser and invalid-key calls return 200 instead of 401.
@skipUnless(settings.ENABLE_OAUTH2, "OAuth2 disabled; auth config is import-time bound")
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

    # A missing/invalid/revoked key can only produce 401 when anonymous traffic is off;
    # with ENABLE_ANONYMOUS_TRAFFIC=True these requests are downgraded to AnonymousUser and
    # return 200. ENABLE_ANONYMOUS_TRAFFIC is read at request time, so overriding it here
    # takes effect (unlike the import-time-bound auth-method list). An *expired* key differs:
    # it 401s regardless of this flag (see the expired test below).
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
        # Arrange -- an expired key is a presented-but-stale credential; it must 401 with an
        # "expired" message even when anonymous traffic is enabled, not fall through to 200.
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
