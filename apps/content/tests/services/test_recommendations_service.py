from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone
from model_bakery import baker
import redis as redis_lib

from apps.content.models import (
    Asset,
    CategoryChoice,
    EditorialRecommendation,
    EditorialRecommendationAsset,
    LicenseChoice,
    StatusChoice,
    UsageEvent,
)
from apps.content.services.recommendations import (
    compute_personalized_recommendations,
    compute_similar_recommendations,
    compute_trending_recommendations,
    get_personalized_asset_ids,
    get_similar_asset_ids,
    get_trending_asset_ids,
    hydrate_visible_assets_in_order,
    list_active_editorial_recommendations,
)
from apps.content.services.recommendations_redis import similar_key
from apps.core.tests.base import BaseTestCase
from apps.users.models import User

# Dev settings run the Django cache on LocMemCache (see config/settings/development.py),
# so get_recommendations_redis() would resolve to None there -- exactly like
# apps.usage_tracking.tasks._get_tracking_redis. usage_tracking's tests mock that
# resolver with a MagicMock; here we point it at a real Redis test DB instead, so the
# scoring assertions below exercise genuine ZADD/ZRANGE/ZSCORE semantics rather than a
# mock's recorded calls. DB 15 is reserved for tests and flushed before/after each test.
_GET_REDIS = "apps.content.services.recommendations.get_recommendations_redis"


def _test_redis_client() -> redis_lib.Redis:
    from urllib.parse import urlparse

    from decouple import config

    parsed = urlparse(config("REDIS_URL", default="redis://localhost:6379/1"))
    return redis_lib.Redis(host=parsed.hostname, port=parsed.port, db=15, decode_responses=True)


class RecommendationsServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.qiraah = baker.make("content.Qiraah", name="Hafs")
        self.riwayah_a = baker.make("content.Riwayah", name="Riwayah A", qiraah=self.qiraah)
        self.riwayah_b = baker.make("content.Riwayah", name="Riwayah B", qiraah=self.qiraah)
        self.reciter_1 = baker.make("content.Reciter", name="Reciter 1")
        self.reciter_2 = baker.make("content.Reciter", name="Reciter 2")

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def _make_recitation(self, **kwargs):
        defaults = {
            "category": CategoryChoice.RECITATION,
            "status": StatusChoice.READY,
            "restricted_for_tenant": False,
            "qiraah": self.qiraah,
        }
        defaults.update(kwargs)
        return baker.make(Asset, **defaults)

    def test_same_reciter_and_riwayah_scores_higher_than_same_riwayah_alone(self):
        # Arrange: source shares reciter+riwayah with `close`, only riwayah with `far`.
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        close = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        far = self._make_recitation(reciter=self.reciter_2, riwayah=self.riwayah_a)

        # Act
        compute_similar_recommendations()
        result = get_similar_asset_ids(source.id)

        # Assert: both appear, but the stronger (reciter+riwayah) match ranks first.
        self.assertEqual([close.id, far.id], result)

    def test_qiraah_match_not_double_counted_when_riwayah_already_matches(self):
        """riwayah implies its qiraah (Asset.save()), so a riwayah match alone should
        score the same as a riwayah+qiraah match -- not double the qiraah weight."""
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        same_riwayah = self._make_recitation(reciter=self.reciter_2, riwayah=self.riwayah_a)
        same_qiraah_only = self._make_recitation(reciter=self.reciter_2, riwayah=self.riwayah_b)

        compute_similar_recommendations()

        same_riwayah_score = self.redis_client.zscore(similar_key(source.id), str(same_riwayah.id))
        same_qiraah_score = self.redis_client.zscore(similar_key(source.id), str(same_qiraah_only.id))

        # riwayah match (weight 2) beats a bare qiraah-only match (weight 1).
        self.assertGreater(same_riwayah_score, same_qiraah_score)

    def test_unrelated_category_asset_is_not_a_candidate(self):
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        unrelated = baker.make(
            Asset,
            category=CategoryChoice.TAFSIR,
            status=StatusChoice.READY,
            restricted_for_tenant=False,
            reciter=None,
            riwayah=None,
            qiraah=None,
        )

        compute_similar_recommendations()
        result = get_similar_asset_ids(source.id)

        self.assertNotIn(unrelated.id, result)

    def test_draft_and_restricted_assets_excluded_from_scoring(self):
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        draft = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a, status=StatusChoice.DRAFT)
        restricted = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a, restricted_for_tenant=True)

        compute_similar_recommendations()
        result = get_similar_asset_ids(source.id)

        self.assertNotIn(draft.id, result)
        self.assertNotIn(restricted.id, result)

    def test_recompute_clears_stale_entries(self):
        """An asset that used to have a match but no longer does (e.g. sibling asset
        deleted) should have its Redis key cleared, not left with stale ids."""
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        sibling = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)

        compute_similar_recommendations()
        self.assertEqual([sibling.id], get_similar_asset_ids(source.id))

        sibling.delete()
        compute_similar_recommendations()

        self.assertEqual([], get_similar_asset_ids(source.id))

    def test_get_similar_asset_ids_respects_limit(self):
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        for _ in range(3):
            self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)

        compute_similar_recommendations()
        result = get_similar_asset_ids(source.id, limit=2)

        self.assertEqual(2, len(result))

    def test_hydrate_drops_ids_no_longer_visible_and_preserves_order(self):
        source = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        visible = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)
        now_restricted = self._make_recitation(reciter=self.reciter_1, riwayah=self.riwayah_a)

        # Simulate the asset having become restricted after the nightly run computed it.
        ordered_ids = [now_restricted.id, visible.id]
        now_restricted.restricted_for_tenant = True
        now_restricted.save()

        hydrated = hydrate_visible_assets_in_order(ordered_ids)

        self.assertEqual([visible.id], [a.id for a in hydrated])
        self.assertNotIn(source.id, [a.id for a in hydrated])


def _make_usage_event(user, asset, usage_kind, days_ago: float = 0) -> UsageEvent:
    """Create a UsageEvent, optionally backdated (created_at is auto_now_add)."""
    event = UsageEvent.objects.create(
        developer_user=user,
        usage_kind=usage_kind,
        asset_id=asset.id,
        effective_license=LicenseChoice.CC0,
    )
    if days_ago:
        UsageEvent.objects.filter(id=event.id).update(created_at=timezone.now() - timedelta(days=days_ago))
        event.refresh_from_db()
    return event


class TrendingRecommendationsServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.user = User.objects.create_user(email="trending@example.com", name="Trending User")

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def _make_asset(self, **kwargs):
        # MUSHAF (not RECITATION) by default: RECITATION assets require reciter+qiraah
        # per the asset_recitation_fields_consistency DB constraint, which these
        # trending tests don't care about (they only care about visibility/usage).
        defaults = {
            "category": CategoryChoice.MUSHAF,
            "status": StatusChoice.READY,
            "restricted_for_tenant": False,
        }
        defaults.update(kwargs)
        return baker.make(Asset, **defaults)

    def test_downloads_outrank_more_numerous_views(self):
        downloaded = self._make_asset()
        _make_usage_event(self.user, downloaded, UsageEvent.UsageKindChoice.FILE_DOWNLOAD)

        viewed = self._make_asset()
        for _ in range(2):
            _make_usage_event(self.user, viewed, UsageEvent.UsageKindChoice.VIEW)

        compute_trending_recommendations()

        self.assertEqual([downloaded.id, viewed.id], get_trending_asset_ids())

    def test_events_outside_window_are_ignored(self):
        stale = self._make_asset()
        _make_usage_event(self.user, stale, UsageEvent.UsageKindChoice.FILE_DOWNLOAD, days_ago=30)

        compute_trending_recommendations()

        self.assertEqual([], get_trending_asset_ids())

    def test_draft_and_restricted_assets_excluded(self):
        draft = self._make_asset(status=StatusChoice.DRAFT)
        _make_usage_event(self.user, draft, UsageEvent.UsageKindChoice.VIEW)
        restricted = self._make_asset(restricted_for_tenant=True)
        _make_usage_event(self.user, restricted, UsageEvent.UsageKindChoice.VIEW)

        compute_trending_recommendations()

        self.assertEqual([], get_trending_asset_ids())

    def test_category_scoped_leaderboard_only_includes_that_category(self):
        mushaf = self._make_asset(category=CategoryChoice.MUSHAF)
        _make_usage_event(self.user, mushaf, UsageEvent.UsageKindChoice.VIEW)
        tafsir = self._make_asset(category=CategoryChoice.TAFSIR)
        _make_usage_event(self.user, tafsir, UsageEvent.UsageKindChoice.VIEW)

        compute_trending_recommendations()

        self.assertEqual([mushaf.id], get_trending_asset_ids(category=CategoryChoice.MUSHAF))
        self.assertEqual([tafsir.id], get_trending_asset_ids(category=CategoryChoice.TAFSIR))
        self.assertCountEqual([mushaf.id, tafsir.id], get_trending_asset_ids())

    def test_recompute_clears_stale_entries(self):
        asset = self._make_asset()
        _make_usage_event(self.user, asset, UsageEvent.UsageKindChoice.VIEW)
        compute_trending_recommendations()
        self.assertEqual([asset.id], get_trending_asset_ids())

        UsageEvent.objects.all().delete()
        compute_trending_recommendations()

        self.assertEqual([], get_trending_asset_ids())


class PersonalizedRecommendationsServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.redis_client = _test_redis_client()
        self.redis_client.flushdb()
        self._redis_patcher = patch(_GET_REDIS, return_value=self.redis_client)
        self._redis_patcher.start()

        self.user = User.objects.create_user(email="personalized@example.com", name="Personalized User")
        self.qiraah = baker.make("content.Qiraah", name="Hafs")
        self.riwayah = baker.make("content.Riwayah", name="Riwayah A", qiraah=self.qiraah)
        self.reciter = baker.make("content.Reciter", name="Reciter 1")

    def tearDown(self):
        self.redis_client.flushdb()
        self._redis_patcher.stop()
        super().tearDown()

    def _make_recitation(self, **kwargs):
        defaults = {
            "category": CategoryChoice.RECITATION,
            "status": StatusChoice.READY,
            "restricted_for_tenant": False,
        }
        defaults.update(kwargs)
        return baker.make(Asset, **defaults)

    def test_recommends_assets_sharing_facets_with_history(self):
        watched = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        _make_usage_event(self.user, watched, UsageEvent.UsageKindChoice.VIEW)
        matching = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        unrelated = self._make_recitation(category=CategoryChoice.TAFSIR)

        compute_personalized_recommendations()
        result = get_personalized_asset_ids(self.user.id)

        self.assertIn(matching.id, result)
        self.assertNotIn(unrelated.id, result)

    def test_excludes_assets_already_in_history(self):
        watched = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        _make_usage_event(self.user, watched, UsageEvent.UsageKindChoice.VIEW)

        compute_personalized_recommendations()

        self.assertNotIn(watched.id, get_personalized_asset_ids(self.user.id))

    def test_user_with_no_history_has_no_precomputed_data(self):
        compute_personalized_recommendations()

        self.assertEqual([], get_personalized_asset_ids(self.user.id))

    def test_history_outside_lookback_window_ignored(self):
        watched = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        _make_usage_event(self.user, watched, UsageEvent.UsageKindChoice.VIEW, days_ago=120)
        self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)

        compute_personalized_recommendations()

        self.assertEqual([], get_personalized_asset_ids(self.user.id))

    def test_recompute_clears_stale_entries(self):
        watched = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        _make_usage_event(self.user, watched, UsageEvent.UsageKindChoice.VIEW)
        matching = self._make_recitation(reciter=self.reciter, riwayah=self.riwayah)
        compute_personalized_recommendations()
        self.assertEqual([matching.id], get_personalized_asset_ids(self.user.id))

        matching.delete()
        compute_personalized_recommendations()

        self.assertEqual([], get_personalized_asset_ids(self.user.id))


class EditorialRecommendationsServiceTest(BaseTestCase):
    def setUp(self):
        super().setUp()

    def _make_asset(self, **kwargs):
        # MUSHAF (not RECITATION) by default: RECITATION assets require reciter+qiraah
        # per the asset_recitation_fields_consistency DB constraint, which these
        # editorial tests don't care about (they only care about visibility).
        defaults = {
            "category": CategoryChoice.MUSHAF,
            "status": StatusChoice.READY,
            "restricted_for_tenant": False,
        }
        defaults.update(kwargs)
        return baker.make(Asset, **defaults)

    def test_returns_active_collection_with_assets_ordered_by_position(self):
        collection = EditorialRecommendation.objects.create(title="Ramadan Picks")
        first, second = self._make_asset(), self._make_asset()
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=second, position=2)
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=first, position=1)

        result = list_active_editorial_recommendations()

        self.assertEqual(1, len(result))
        self.assertEqual([first.id, second.id], [a.id for a in result[0]["assets"]])

    def test_excludes_inactive_collection(self):
        collection = EditorialRecommendation.objects.create(title="Draft Collection", is_active=False)
        EditorialRecommendationAsset.objects.create(recommendation=collection, asset=self._make_asset())

        self.assertEqual([], list_active_editorial_recommendations())

    def test_excludes_collection_outside_active_window(self):
        future = EditorialRecommendation.objects.create(title="Future", starts_at=timezone.now() + timedelta(days=7))
        EditorialRecommendationAsset.objects.create(recommendation=future, asset=self._make_asset())
        expired = EditorialRecommendation.objects.create(title="Expired", ends_at=timezone.now() - timedelta(days=1))
        EditorialRecommendationAsset.objects.create(recommendation=expired, asset=self._make_asset())

        self.assertEqual([], list_active_editorial_recommendations())

    def test_excludes_collection_with_no_visible_assets(self):
        collection = EditorialRecommendation.objects.create(title="All Hidden")
        EditorialRecommendationAsset.objects.create(
            recommendation=collection, asset=self._make_asset(status=StatusChoice.DRAFT)
        )
        EditorialRecommendationAsset.objects.create(
            recommendation=collection, asset=self._make_asset(restricted_for_tenant=True)
        )

        self.assertEqual([], list_active_editorial_recommendations())
