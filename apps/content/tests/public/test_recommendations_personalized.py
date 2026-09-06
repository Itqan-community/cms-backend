from unittest.mock import patch

from model_bakery import baker
import redis as redis_lib

from apps.content.models import Asset, CategoryChoice, LicenseChoice, StatusChoice, UsageEvent
from apps.content.services.recommendations import compute_trending_recommendations
from apps.content.services.recommendations_redis import personalized_key
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import APIKey, User

# See test_recommendations_service.py for why we point the resolver at a real Redis
# test DB rather than relying on dev settings' LocMemCache (which resolves to None).
_GET_REDIS = "apps.content.services.recommendations.get_recommendations_redis"


def _test_redis_client() -> redis_lib.Redis:
    from urllib.parse import urlparse

    from decouple import config

    parsed = urlparse(config("REDIS_URL", default="redis://localhost:6379/1"))
    return redis_lib.Redis(host=parsed.hostname, port=parsed.port, db=15, decode_responses=True)


class PersonalizedRecommendationsEndpointTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.publisher = baker.make(Publisher)
        self.personalized_asset = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
        )
        self.trending_asset = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
        )

        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def _authenticate_with_api_key(self, user: User) -> None:
        _, raw_key = APIKey.objects.create_key(name="test-key", user=user)
        self.client.credentials(HTTP_X_API_KEY=raw_key)

    def test_requires_authentication(self):
        response = self.client.get("/recommendations/personalized/")

        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_required", response.json()["error_name"])

    def test_returns_precomputed_personalized_assets(self):
        self.redis_client.zadd(personalized_key(self.user.id), {str(self.personalized_asset.id): 5})
        self._authenticate_with_api_key(self.user)

        response = self.client.get("/recommendations/personalized/")

        self.assertEqual(200, response.status_code, response.content)
        ids = [item["id"] for item in response.json()]
        self.assertEqual([self.personalized_asset.id], ids)

    def test_falls_back_to_trending_when_no_personalized_data(self):
        UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=UsageEvent.UsageKindChoice.VIEW,
            asset_id=self.trending_asset.id,
            effective_license=LicenseChoice.CC0,
        )
        compute_trending_recommendations()
        self._authenticate_with_api_key(self.user)

        response = self.client.get("/recommendations/personalized/")

        self.assertEqual(200, response.status_code, response.content)
        ids = [item["id"] for item in response.json()]
        self.assertEqual([self.trending_asset.id], ids)
