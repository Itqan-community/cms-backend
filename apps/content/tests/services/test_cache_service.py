import os

import redis
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from unittest import skipUnless

from apps.core.tests import BaseTestCase


@skipUnless(
    os.getenv("ENABLE_REDIS_TESTS") == "1",
    "Set ENABLE_REDIS_TESTS=1 to run Redis integration tests",
)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        }
    }
)
class RedisCacheIntegrationTests(BaseTestCase):
    def test_redis_connection_and_cache_roundtrip(self):
        # Low-level ping using redis-py
        url = settings.CACHES["default"]["LOCATION"]
        client = redis.from_url(url)
        self.assertTrue(client.ping())

        # Django cache roundtrip
        cache_key = "reciter_stats_integration_test"
        cache.set(cache_key, "ok", timeout=10)
        self.assertEqual(cache.get(cache_key), "ok")
