from unittest.mock import patch

from model_bakery import baker
from oauth2_provider.models import Application
import redis as redis_lib

from apps.content.models import Asset, CategoryChoice, StatusChoice
from apps.content.services.recommendations import compute_similar_recommendations
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# See test_recommendations_service.py for why we point the resolver at a real Redis
# test DB rather than relying on dev settings' LocMemCache (which resolves to None).
_GET_REDIS = "apps.content.services.recommendations.get_recommendations_redis"


def _test_redis_client() -> redis_lib.Redis:
    # Dev/CI settings force CACHES to LocMemCache (see config/settings/development.py),
    # so we can't route through django-redis here -- resolve the host the same way
    # base.py resolves REDIS_URL, which is "localhost" natively and "redis" in CI's
    # docker-compose network.
    from urllib.parse import urlparse

    from decouple import config

    parsed = urlparse(config("REDIS_URL", default="redis://localhost:6379/1"))
    return redis_lib.Redis(host=parsed.hostname, port=parsed.port, db=15, decode_responses=True)


class SimilarRecommendationsEndpointTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.publisher = baker.make(Publisher)
        self.qiraah = baker.make("content.Qiraah", name="Hafs")
        self.riwayah = baker.make("content.Riwayah", name="Riwayah A", qiraah=self.qiraah)
        self.reciter = baker.make("content.Reciter", name="Reciter 1")

        self.source = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
        )
        self.similar = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
        )

        self.user = User.objects.create_user(email="oauthuser@example.com", name="OAuth User")
        self.app = Application.objects.create(
            user=self.user,
            name="App 1",
            client_type="confidential",
            authorization_grant_type="password",
        )

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def test_returns_precomputed_similar_assets(self):
        compute_similar_recommendations()
        self.authenticate_client(self.app)

        response = self.client.get(f"/recommendations/similar/{self.source.id}/")

        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        ids = [item["id"] for item in body]
        self.assertEqual([self.similar.id], ids)
        self.assertEqual(self.reciter.id, body[0]["reciter"]["id"])
        self.assertEqual(self.publisher.id, body[0]["publisher"]["id"])

    def test_asset_with_no_matches_returns_empty_list_not_error(self):
        # A different category (with no reciter/riwayah/qiraah, per the recitation-only
        # constraint) shares nothing with self.source/self.similar, so it scores zero
        # candidates -- the only way to get a truly "lonely" asset here, since sharing
        # `category` alone is worth a point.
        lonely = baker.make(
            Asset,
            category=CategoryChoice.MUSHAF,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            publisher=self.publisher,
            reciter=None,
            riwayah=None,
            qiraah=None,
        )
        compute_similar_recommendations()
        self.authenticate_client(self.app)

        response = self.client.get(f"/recommendations/similar/{lonely.id}/")

        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual([], response.json())

    def test_nonexistent_asset_returns_404(self):
        self.authenticate_client(self.app)

        response = self.client.get("/recommendations/similar/999999/")

        self.assertEqual(404, response.status_code)

    def test_draft_asset_returns_404(self):
        draft = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.DRAFT,
            restricted_for_tenant=False,
            publisher=self.publisher,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
        )
        self.authenticate_client(self.app)

        response = self.client.get(f"/recommendations/similar/{draft.id}/")

        self.assertEqual(404, response.status_code)

    def test_restricted_candidate_is_excluded_from_results(self):
        restricted_similar = baker.make(
            Asset,
            category=CategoryChoice.RECITATION,
            status=StatusChoice.READY,
            restricted_for_tenant=True,
            publisher=self.publisher,
            reciter=self.reciter,
            riwayah=self.riwayah,
            qiraah=self.qiraah,
        )
        compute_similar_recommendations()

        # Recompute happens while restricted_for_tenant=True, so it's never scored in
        # the first place -- confirms the source-side filter, not just hydration-time
        # filtering.
        self.authenticate_client(self.app)
        response = self.client.get(f"/recommendations/similar/{self.source.id}/")

        ids = [item["id"] for item in response.json()]
        self.assertNotIn(restricted_similar.id, ids)

    def test_endpoint_requires_no_special_auth_beyond_public_api(self):
        """Discovery metadata endpoint -- readable the same way /reciters/ is, no
        enforce_asset_access_on_public_api gate (unlike /recitations/{id}/)."""
        compute_similar_recommendations()

        response = self.client.get(f"/recommendations/similar/{self.source.id}/")

        # No auth configured at all: depends on ENABLE_ANONYMOUS_TRAFFIC, but should
        # never be a 401/403 from an asset-content access gate.
        self.assertIn(response.status_code, (200, 401))
        if response.status_code == 401:
            self.assertNotEqual("access_denied", response.json().get("error_name"))
