from decouple import config
from django.test import override_settings

from apps.content.services.recommendations_redis import (
    get_recommendations_redis,
    reset_recommendations_redis_cache,
)
from apps.core.tests.base import BaseTestCase

# The test suite runs on development settings (LocMemCache), where the recommendations
# client resolves to None. Point the default cache at a real django-redis backend so the
# builder runs the same code path as production.
_DJANGO_REDIS_CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}


class GetRecommendationsRedisTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        reset_recommendations_redis_cache()

    def tearDown(self):
        reset_recommendations_redis_cache()
        super().tearDown()

    @override_settings(CACHES=_DJANGO_REDIS_CACHES)
    def test_get_recommendations_redis_where_cache_is_django_redis_should_return_working_client_on_dedicated_db(
        self,
    ):
        # Arrange
        # (django-redis injects connection-only kwargs such as `parser_class` into the
        # cache pool's connection_kwargs, which `redis.Redis(**kwargs)` rejects.)

        # Act
        client = get_recommendations_redis()

        # Assert
        self.assertIsNotNone(client)
        self.assertTrue(client.ping())
        self.assertEqual(3, client.connection_pool.connection_kwargs["db"])
        client.set("recommendations:test-key", "value", ex=5)
        self.assertEqual("value", client.get("recommendations:test-key"))
        client.delete("recommendations:test-key")

    def test_get_recommendations_redis_where_cache_is_not_django_redis_should_return_none(self):
        # Arrange (development settings use LocMemCache)

        # Act
        client = get_recommendations_redis()

        # Assert
        self.assertIsNone(client)
