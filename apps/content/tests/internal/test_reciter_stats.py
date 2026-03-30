import unittest
from unittest.mock import patch

from django.core.cache import cache
from model_bakery import baker

from apps.content.api.internal.reciter_stats import RECITER_STATS_CACHE_KEY, RECITER_STATS_TTL
from apps.content.models import Reciter
from apps.core.tests import BaseTestCase
from apps.users.models import User

# TODO: to not block merging contributor PR, consider moving this test to tests/portal/ and update tests naming to match preferred naming conventions and be consistent with other tests


# These tests require a live Redis instance and are skipped in CI/CD until Redis caching is configured in the project.
# The implementation and tests are correct — do not remove or refactor them. Re-enable them by removing the @unittest.skip decorator once Redis is set up.
# All tests were passing locally with a Redis instance, confirming the correctness of the implementation.


@unittest.skip("Requires Redis cache — skipped until Redis is configured in CI/CD")
class ReciterStatsCacheTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        # These tests don't need storage mocking
        return

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = baker.make(User, email="reciter-stats@example.com", is_active=True)

    def test_requires_authentication(self):
        self.authenticate_user(None)
        response = self.client.get("/cms-api/reciters/stats/")
        self.assertIn(response.status_code, (401, 403), response.content)

    def test_first_call_hits_db_and_sets_cache(self):
        self.authenticate_user(self.user)

        # Arrange: have at least one reciter so aggregate makes sense
        Reciter.objects.create(name="Test Reciter 1")

        with patch("apps.content.api.internal.reciter_stats.Reciter.objects.aggregate") as aggregate_mock:
            aggregate_mock.return_value = {
                "registered_reciters": 1,
                "contemporary_reciters": 0,
                "nationalities": 0,
            }

            # Act
            response = self.client.get("/cms-api/reciters/stats/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        aggregate_mock.assert_called_once()

        cached_value = cache.get(RECITER_STATS_CACHE_KEY)
        self.assertIsNotNone(cached_value)
        self.assertEqual(
            cached_value,
            {
                "registered_reciters": 1,
                "contemporary_reciters": 0,
                "nationalities": 0,
            },
        )

    def test_second_call_uses_cache_and_skips_db(self):
        self.authenticate_user(self.user)

        # Arrange: simulate cache already populated
        cache.set(
            RECITER_STATS_CACHE_KEY,
            {
                "registered_reciters": 5,
                "contemporary_reciters": 2,
                "nationalities": 3,
            },
            timeout=RECITER_STATS_TTL,
        )

        with patch("apps.content.api.internal.reciter_stats.Reciter.objects.aggregate") as aggregate_mock:
            # Act
            response = self.client.get("/cms-api/reciters/stats/")

        # Assert
        self.assertEqual(response.status_code, 200, response.content)
        aggregate_mock.assert_not_called()
        data = response.json()
        self.assertEqual(data["registered_reciters"], 5)
        self.assertEqual(data["contemporary_reciters"], 2)
        self.assertEqual(data["nationalities"], 3)

    def test_cache_is_invalidated_on_reciter_save(self):
        self.authenticate_user(self.user)

        # Arrange
        cache.set(
            RECITER_STATS_CACHE_KEY,
            {
                "registered_reciters": 5,
                "contemporary_reciters": 2,
                "nationalities": 3,
            },
            timeout=RECITER_STATS_TTL,
        )
        self.assertIsNotNone(cache.get(RECITER_STATS_CACHE_KEY))

        # Act: saving a reciter should trigger the signal and clear cache
        Reciter.objects.create(name="New Reciter")

        # Assert
        self.assertIsNone(cache.get(RECITER_STATS_CACHE_KEY))

    def test_cache_is_invalidated_on_reciter_delete(self):
        self.authenticate_user(self.user)

        # Arrange
        reciter = Reciter.objects.create(name="To Delete")
        cache.set(
            RECITER_STATS_CACHE_KEY,
            {
                "registered_reciters": 5,
                "contemporary_reciters": 2,
                "nationalities": 3,
            },
            timeout=RECITER_STATS_TTL,
        )
        self.assertIsNotNone(cache.get(RECITER_STATS_CACHE_KEY))

        # Act: deleting a reciter should trigger the signal and clear cache
        reciter.delete()

        # Assert
        self.assertIsNone(cache.get(RECITER_STATS_CACHE_KEY))
