"""
Tests for GET /cms-api/recitations/library-stats/ (recitations library statistics).

Covers: auth, correct counts, Redis cache hit/miss, cache invalidation on Riwayah/Reciter/Asset change.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from model_bakery import baker

from apps.content.api.internal.recitations_library_stats import (
    RECITATIONS_LIBRARY_STATS_CACHE_KEY,
    RECITATIONS_LIBRARY_STATS_TTL,
)
from apps.content.models import Asset, Qiraah, Reciter, Resource, Riwayah
from apps.core.tests import BaseTestCase
from apps.publishers.models import Publisher
from apps.users.models import User

# TODO: to not block merging contributor PR, consider moving this test to tests/portal/ and update tests naming to match preferred naming conventions and be consistent with other tests


@override_settings(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": "redis://localhost:6379/1"}
    }
)
class RecitationsLibraryStatsTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        # Skip BaseTestCase storage mocking; these tests don't need it.
        return

    def setUp(self):
        super().setUp()
        cache.clear()
        self.user = baker.make(User, email="library-stats@example.com", is_active=True)

    def test_requires_authentication(self):
        self.authenticate_user(None)
        response = self.client.get("/cms-api/recitations/library-stats/")
        self.assertIn(response.status_code, (401, 403), response.content)

    def test_returns_correct_counts(self):
        """Endpoint returns total_riwayas, total_reciters, total_recitations from DB."""
        self.authenticate_user(self.user)

        qiraah = baker.make(Qiraah, name="Qiraah Asim", is_active=True)
        riwayah1 = baker.make(Riwayah, name="Hafs", qiraah=qiraah, is_active=True)
        riwayah2 = baker.make(Riwayah, name="Warsh", qiraah=qiraah, is_active=True)
        reciter1 = baker.make(Reciter, name="Reciter One", is_active=True)
        reciter2 = baker.make(Reciter, name="Reciter Two", is_active=True)
        publisher = baker.make(Publisher, name="Test Publisher")
        resource = baker.make(
            Resource,
            name="Recitation Resource",
            publisher=publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        baker.make(
            Asset,
            name="Recitation Asset 1",
            category=Resource.CategoryChoice.RECITATION,
            resource=resource,
            reciter=reciter1,
            riwayah=riwayah1,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0",
            language="ar",
        )
        baker.make(
            Asset,
            name="Recitation Asset 2",
            category=Resource.CategoryChoice.RECITATION,
            resource=resource,
            reciter=reciter2,
            riwayah=riwayah2,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0",
            language="ar",
        )

        response = self.client.get("/cms-api/recitations/library-stats/")

        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["total_riwayas"], 2)
        self.assertEqual(data["total_reciters"], 2)
        self.assertEqual(data["total_recitations"], 2)

    def test_first_call_hits_db_and_sets_cache(self):
        """First request computes stats and caches them."""
        self.authenticate_user(self.user)
        baker.make(Riwayah, name="Hafs", qiraah=baker.make(Qiraah, name="Asim"), is_active=True)
        baker.make(Reciter, name="Reciter A", is_active=True)

        with patch("apps.content.api.internal.recitations_library_stats._compute_library_stats") as compute_mock:
            compute_mock.return_value = {
                "total_riwayas": 5,
                "total_reciters": 10,
                "total_recitations": 20,
            }
            response = self.client.get("/cms-api/recitations/library-stats/")

        self.assertEqual(response.status_code, 200, response.content)
        compute_mock.assert_called_once()
        cached = cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY)
        self.assertEqual(
            cached,
            {"total_riwayas": 5, "total_reciters": 10, "total_recitations": 20},
        )

    def test_second_call_uses_cache_and_skips_compute(self):
        """Second request returns cached value without calling _compute_library_stats."""
        self.authenticate_user(self.user)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 2, "total_recitations": 3},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )

        with patch("apps.content.api.internal.recitations_library_stats._compute_library_stats") as compute_mock:
            response = self.client.get("/cms-api/recitations/library-stats/")

        self.assertEqual(response.status_code, 200, response.content)
        compute_mock.assert_not_called()
        data = response.json()
        self.assertEqual(data["total_riwayas"], 1)
        self.assertEqual(data["total_reciters"], 2)
        self.assertEqual(data["total_recitations"], 3)

    def test_cache_invalidated_on_riwayah_save(self):
        self.authenticate_user(self.user)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        qiraah = baker.make(Qiraah, name="Asim", is_active=True)
        baker.make(Riwayah, name="New Riwayah", qiraah=qiraah, is_active=True)
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_cache_invalidated_on_riwayah_delete(self):
        self.authenticate_user(self.user)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        qiraah = baker.make(Qiraah, name="Asim", is_active=True)
        riwayah = baker.make(Riwayah, name="To Delete", qiraah=qiraah, is_active=True)
        riwayah.delete()
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_cache_invalidated_on_reciter_save(self):
        self.authenticate_user(self.user)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        baker.make(Reciter, name="New Reciter", is_active=True)
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_cache_invalidated_on_reciter_delete(self):
        self.authenticate_user(self.user)
        reciter = baker.make(Reciter, name="To Delete", is_active=True)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        reciter.delete()
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_cache_invalidated_on_recitation_asset_save(self):
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Pub")
        resource = baker.make(
            Resource,
            name="Res",
            publisher=publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        reciter = baker.make(Reciter, name="R", is_active=True)
        qiraah = baker.make(Qiraah, name="Q", is_active=True)
        riwayah = baker.make(Riwayah, name="Hafs", qiraah=qiraah, is_active=True)
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 0},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        baker.make(
            Asset,
            name="New Recitation",
            category=Resource.CategoryChoice.RECITATION,
            resource=resource,
            reciter=reciter,
            riwayah=riwayah,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0",
            language="ar",
        )
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_cache_invalidated_on_recitation_asset_delete(self):
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Pub")
        resource = baker.make(
            Resource,
            name="Res",
            publisher=publisher,
            category=Resource.CategoryChoice.RECITATION,
            status=Resource.StatusChoice.READY,
        )
        reciter = baker.make(Reciter, name="R", is_active=True)
        qiraah = baker.make(Qiraah, name="Q", is_active=True)
        riwayah = baker.make(Riwayah, name="Hafs", qiraah=qiraah, is_active=True)
        asset = baker.make(
            Asset,
            name="Recitation To Delete",
            category=Resource.CategoryChoice.RECITATION,
            resource=resource,
            reciter=reciter,
            riwayah=riwayah,
            license="CC0",
            file_size="1 MB",
            format="mp3",
            version="1.0",
            language="ar",
        )
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        asset.delete()
        self.assertIsNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))

    def test_non_recitation_asset_save_does_not_invalidate_cache(self):
        """Saving a non-recitation Asset (e.g. TAFSIR) must not clear library stats cache."""
        self.authenticate_user(self.user)
        publisher = baker.make(Publisher, name="Pub")
        resource = baker.make(
            Resource,
            name="Tafsir Res",
            publisher=publisher,
            category=Resource.CategoryChoice.TAFSIR,
            status=Resource.StatusChoice.READY,
        )
        cache.set(
            RECITATIONS_LIBRARY_STATS_CACHE_KEY,
            {"total_riwayas": 1, "total_reciters": 1, "total_recitations": 1},
            timeout=RECITATIONS_LIBRARY_STATS_TTL,
        )
        baker.make(
            Asset,
            name="Tafsir Asset",
            category=Resource.CategoryChoice.TAFSIR,
            resource=resource,
            license="CC0",
            file_size="1 MB",
            format="pdf",
            version="1.0",
            language="ar",
        )
        self.assertIsNotNone(cache.get(RECITATIONS_LIBRARY_STATS_CACHE_KEY))
