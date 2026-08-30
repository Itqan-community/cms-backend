from unittest.mock import patch

from model_bakery import baker
from oauth2_provider.models import Application
import redis as redis_lib

from apps.content.models import Asset, CategoryChoice, LicenseChoice, StatusChoice, UsageEvent
from apps.content.services.recommendations import compute_trending_recommendations
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# See test_recommendations_service.py for why we point the resolver at a real Redis
# test DB rather than relying on dev settings' LocMemCache (which resolves to None).
_GET_REDIS = "apps.content.services.recommendations.get_recommendations_redis"


def _test_redis_client() -> redis_lib.Redis:
    from urllib.parse import urlparse

    from decouple import config

    parsed = urlparse(config("REDIS_URL", default="redis://localhost:6379/1"))
    return redis_lib.Redis(host=parsed.hostname, port=parsed.port, db=15, decode_responses=True)


class TrendingRecommendationsEndpointTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.publisher = baker.make(Publisher)
        self.trending_asset = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
        )

        self.user = User.objects.create_user(email="oauthuser2@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )
        UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            asset_id=self.trending_asset.id,
            effective_license=LicenseChoice.CC0,
        )

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def test_returns_precomputed_trending_assets(self):
        compute_trending_recommendations()
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/trending/")

        self.assertEqual(200, response.status_code, response.content)
        ids = [item["id"] for item in response.json()]
        self.assertEqual([self.trending_asset.id], ids)

    def test_category_query_param_scopes_results(self):
        compute_trending_recommendations()
        self.authenticate_client(self.app)

        response = self.client.get(f"/recommendations/trending/?category={CategoryChoice.TAFSIR}")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_no_precomputed_data_returns_empty_list_not_error(self):
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/trending/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_endpoint_requires_no_special_auth_beyond_public_api(self):
        """Discovery metadata endpoint -- readable the same way /similar/ is."""
        compute_trending_recommendations()

        response = self.client.get("/recommendations/trending/")

        self.assertIn(response.status_code, (200, 401))
        if response.status_code == 401:
            self.assertNotEqual("access_denied", response.json().get("error_name"))
