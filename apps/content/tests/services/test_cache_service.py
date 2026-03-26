import unittest

from django.conf import settings
from django.core.cache import cache
import redis

from apps.core.tests import BaseTestCase


@unittest.skip("Requires Redis cache — skipped until Redis is configured in CI/CD")
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
