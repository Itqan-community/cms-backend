"""Content recommendation scoring (see GitHub issue #226).

Four recommendation surfaces:
- similar: shared reciter/riwayah/qiraah/category facets between two assets.
- trending: recent usage-event popularity, weighted by event kind.
- personalized: a user's own recent usage history, scored against the catalog with the
  same facet weights as `similar`, falling back to trending when a user has no
  precomputed data (new account, or a history too narrow to score any candidates).
- editorial: admin-curated collections (apps.content.models.EditorialRecommendation),
  read straight from the DB -- no precompute/cache, since editorial content changes
  rarely and the query is already small and indexed.

Design notes:
- Candidate generation is facet-indexed, not O(n^2): for each asset (or user profile)
  we only ever compare against the (typically small) sets of other assets sharing the
  same reciter, riwayah, qiraah, or category, rather than scanning the whole catalog.
- Riwayah/qiraah don't double-count: a qiraah-match point is only awarded when the
  riwayah doesn't already match, since (per Asset.save()) riwayah implies its qiraah.
- Only READY assets that are visible on public surfaces (restricted_for_tenant=False)
  are considered as candidates or sources, so recommendations never surface or point at
  content that shouldn't appear on the public developers API.
- similar/trending/personalized results are written to Redis as sorted sets (see
  recommendations_redis) by nightly/periodic Celery tasks; the get_*_asset_ids readers
  only read, they never compute inline.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import logging

from django.db.models import Count, Q
from django.utils import timezone

from apps.content.models import Asset, CategoryChoice, EditorialRecommendation, StatusChoice, UsageEvent
from apps.content.services.recommendations_redis import (
    get_recommendations_redis,
    personalized_key,
    similar_key,
    trending_key,
)

logger = logging.getLogger(__name__)

# How many asset ids to keep per source asset / category / user.
SIMILAR_TOP_N = 10
TRENDING_TOP_N = 10
PERSONALIZED_TOP_N = 10

# Score weights. Same reciter + riwayah is the strongest signal (same person, same
# recitation style); category is the weakest (broad content-type match only). Shared by
# similar-content scoring and personalized scoring (a user's history plays the "source
# asset" role there).
_WEIGHT_RECITER = 3
_WEIGHT_RIWAYAH = 2
_WEIGHT_QIRAAH = 1  # only applied when riwayah doesn't already match
_WEIGHT_CATEGORY = 1

# TTL on similar:*/personalized:* keys: nightly recompute refreshes them well within
# this window, but a TTL keeps a paused/broken beat schedule from serving arbitrarily
# stale data forever.
SIMILAR_KEY_TTL_SECONDS = 60 * 60 * 48  # 48 hours
PERSONALIZED_KEY_TTL_SECONDS = 60 * 60 * 48  # 48 hours

# Trending recomputes far more often than similar/personalized (it's meant to reflect
# recent activity), so its window and TTL are both much shorter.
TRENDING_WINDOW_DAYS = 7
TRENDING_KEY_TTL_SECONDS = 60 * 60 * 2  # 2 hours

# How many of a user's most recent interactions to build their facet profile from.
# Bounds personalized-recompute work per user regardless of how much history they have.
PERSONALIZED_HISTORY_LIMIT = 50
PERSONALIZED_LOOKBACK_DAYS = 90

# Downloads are a stronger "this user liked it" signal than a view; API access sits
# in between (programmatic interest, but not necessarily a human preference).
_USAGE_KIND_WEIGHT = {
    UsageEvent.UsageKindChoice.FILE_DOWNLOAD: 3,
    UsageEvent.UsageKindChoice.API_ACCESS: 2,
    UsageEvent.UsageKindChoice.VIEW: 1,
}


def _visible_asset_values() -> list[dict]:
    """READY, publicly-visible assets, as plain dicts for cheap in-memory scoring."""
    return list(
        Asset.objects.filter(
            status=StatusChoice.READY,
            restricted_for_tenant=False,
        ).values("id", "category", "reciter_id", "riwayah_id", "qiraah_id")
    )


def _build_facet_index(assets: list[dict]):
    """Index `assets` by reciter/riwayah/qiraah/category for O(1) candidate lookups."""
    by_reciter: dict[int, set[int]] = defaultdict(set)
    by_riwayah: dict[int, set[int]] = defaultdict(set)
    by_qiraah: dict[int, set[int]] = defaultdict(set)
    by_category: dict[str, set[int]] = defaultdict(set)
    asset_by_id: dict[int, dict] = {}

    for a in assets:
        asset_by_id[a["id"]] = a
        if a["reciter_id"]:
            by_reciter[a["reciter_id"]].add(a["id"])
        if a["riwayah_id"]:
            by_riwayah[a["riwayah_id"]].add(a["id"])
        if a["qiraah_id"]:
            by_qiraah[a["qiraah_id"]].add(a["id"])
        by_category[a["category"]].add(a["id"])

    return by_reciter, by_riwayah, by_qiraah, by_category, asset_by_id


def _candidate_ids(a: dict, by_reciter, by_riwayah, by_qiraah, by_category) -> set[int]:
    """Union of every facet bucket `a` belongs to -- its full candidate pool."""
    candidates: set[int] = set()
    if a["reciter_id"]:
        candidates |= by_reciter[a["reciter_id"]]
    if a["riwayah_id"]:
        candidates |= by_riwayah[a["riwayah_id"]]
    if a["qiraah_id"]:
        candidates |= by_qiraah[a["qiraah_id"]]
    candidates |= by_category[a["category"]]
    return candidates


def _pair_score(a: dict, other: dict) -> int:
    """Facet-overlap score between two asset value-dicts (order-independent)."""
    score = 0
    riwayah_match = bool(a["riwayah_id"]) and a["riwayah_id"] == other["riwayah_id"]

    if a["reciter_id"] and a["reciter_id"] == other["reciter_id"]:
        score += _WEIGHT_RECITER
    if riwayah_match:
        score += _WEIGHT_RIWAYAH
    elif a["qiraah_id"] and a["qiraah_id"] == other["qiraah_id"]:
        score += _WEIGHT_QIRAAH
    if a["category"] == other["category"]:
        score += _WEIGHT_CATEGORY

    return score


def _score_pairs(assets: list[dict]) -> dict[int, dict[int, int]]:
    """Return {asset_id: {other_asset_id: score}} using facet-indexed candidate sets."""
    by_reciter, by_riwayah, by_qiraah, by_category, asset_by_id = _build_facet_index(assets)
    scores: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for a in assets:
        asset_id = a["id"]
        candidates = _candidate_ids(a, by_reciter, by_riwayah, by_qiraah, by_category)
        candidates.discard(asset_id)

        for other_id in candidates:
            score = _pair_score(a, asset_by_id[other_id])
            if score > 0:
                scores[asset_id][other_id] = score

    return scores


def _score_profile_against_catalog(
    profile_assets: list[dict],
    exclude_ids: set[int],
    by_reciter,
    by_riwayah,
    by_qiraah,
    by_category,
    asset_by_id,
) -> dict[int, int]:
    """Score every catalog candidate against a user's facet profile (their history).

    Scores accumulate across profile items: an asset matching several of a user's past
    picks outranks one matching only one, same as compute_similar_recommendations would
    rank a "matches on more facets" asset higher.
    """
    scores: dict[int, int] = defaultdict(int)
    for p in profile_assets:
        candidates = _candidate_ids(p, by_reciter, by_riwayah, by_qiraah, by_category)
        for other_id in candidates:
            if other_id in exclude_ids:
                continue
            score = _pair_score(p, asset_by_id[other_id])
            if score > 0:
                scores[other_id] += score

    return scores


def compute_similar_recommendations() -> dict:
    """Recompute similar-asset scores for every READY, public asset and write to Redis.

    Intended to run nightly via Celery beat (compute_similar_recommendations_task).
    Assets with no scored candidates get their key deleted rather than left stale from
    a previous run, so a since-removed/rescoped asset doesn't keep surfacing old
    recommendations.

    Returns a small summary dict for logging/observability.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        logger.warning("compute_similar_recommendations: no Redis available, skipping")
        return {"assets_scored": 0, "keys_written": 0}

    assets = _visible_asset_values()
    scores = _score_pairs(assets)

    keys_written = 0
    with redis_client.pipeline() as pipe:
        for a in assets:
            asset_id = a["id"]
            key = similar_key(asset_id)
            pipe.delete(key)
            asset_scores = scores.get(asset_id, {})
            if not asset_scores:
                continue
            top = sorted(asset_scores.items(), key=lambda kv: kv[1], reverse=True)[:SIMILAR_TOP_N]
            pipe.zadd(key, {str(other_id): score for other_id, score in top})
            pipe.expire(key, SIMILAR_KEY_TTL_SECONDS)
            keys_written += 1
        pipe.execute()

    logger.info(f"compute_similar_recommendations: scored {len(assets)} assets, wrote {keys_written} keys")
    return {"assets_scored": len(assets), "keys_written": keys_written}


def get_similar_asset_ids(asset_id: int, limit: int = SIMILAR_TOP_N) -> list[int]:
    """Read precomputed similar-asset ids for `asset_id`, most similar first.

    Returns an empty list when Redis is unavailable or no precomputed entry exists
    (e.g. asset created after the last nightly run, or genuinely has no matches) —
    callers should treat that as "no recommendations yet", not an error.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        return []

    raw_ids = redis_client.zrevrange(similar_key(asset_id), 0, limit - 1)
    return [int(raw_id) for raw_id in raw_ids]


def hydrate_visible_assets_in_order(asset_ids: list[int]) -> list[Asset]:
    """Fetch Assets for `asset_ids`, filtered to still-visible ones, preserving order.

    Precomputed ids can go stale between the nightly run and the request (asset
    unpublished, restricted, or deleted since) — those are silently dropped rather than
    erroring, matching how the recitation-tracks endpoint treats cache/DB drift.
    """
    if not asset_ids:
        return []

    qs = Asset.objects.filter(
        id__in=asset_ids,
        status=StatusChoice.READY,
        restricted_for_tenant=False,
    ).select_related("publisher", "reciter", "riwayah", "qiraah")

    by_id = {a.id: a for a in qs}
    return [by_id[aid] for aid in asset_ids if aid in by_id]


def compute_trending_recommendations() -> dict:
    """Recompute trending scores from recent usage events and write to Redis.

    Scores every visible asset that received a usage event in the trailing
    TRENDING_WINDOW_DAYS, weighted by event kind (a download counts for more than a
    view -- see _USAGE_KIND_WEIGHT), and writes one global leaderboard plus one per
    CategoryChoice. Intended to run frequently via Celery beat
    (compute_trending_recommendations_task): unlike similar/personalized, "trending"
    is meant to track recent activity, not a nightly snapshot.

    Every trending:* key (global + all categories) is deleted before rewriting, even
    when a category has no qualifying events this run, so a category that cools off
    doesn't keep serving a stale leaderboard.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        logger.warning("compute_trending_recommendations: no Redis available, skipping")
        return {"assets_scored": 0, "keys_written": 0}

    since = timezone.now() - timedelta(days=TRENDING_WINDOW_DAYS)
    visible_by_id = {a["id"]: a for a in _visible_asset_values()}

    event_counts = (
        UsageEvent.objects.filter(created_at__gte=since, asset_id__in=visible_by_id.keys())
        .values("asset_id", "usage_kind")
        .annotate(n=Count("id"))
    )

    scores: dict[int, float] = defaultdict(float)
    for row in event_counts:
        scores[row["asset_id"]] += _USAGE_KIND_WEIGHT.get(row["usage_kind"], 1) * row["n"]

    by_category: dict[str, dict[int, float]] = defaultdict(dict)
    for asset_id, score in scores.items():
        category = visible_by_id[asset_id]["category"]
        by_category[category][asset_id] = score

    keys_written = 0
    with redis_client.pipeline() as pipe:
        pipe.delete(trending_key())
        for category in CategoryChoice.values:
            pipe.delete(trending_key(category))

        if scores:
            top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:TRENDING_TOP_N]
            pipe.zadd(trending_key(), {str(asset_id): score for asset_id, score in top})
            pipe.expire(trending_key(), TRENDING_KEY_TTL_SECONDS)
            keys_written += 1

        for category, category_scores in by_category.items():
            top = sorted(category_scores.items(), key=lambda kv: kv[1], reverse=True)[:TRENDING_TOP_N]
            key = trending_key(category)
            pipe.zadd(key, {str(asset_id): score for asset_id, score in top})
            pipe.expire(key, TRENDING_KEY_TTL_SECONDS)
            keys_written += 1
        pipe.execute()

    logger.info(f"compute_trending_recommendations: scored {len(scores)} assets, wrote {keys_written} keys")
    return {"assets_scored": len(scores), "keys_written": keys_written}


def get_trending_asset_ids(category: str | None = None, limit: int = TRENDING_TOP_N) -> list[int]:
    """Read precomputed trending asset ids, most popular first.

    Returns an empty list when Redis is unavailable or nothing has been computed yet
    (or nothing qualifies for the requested/unrecognised category) -- callers treat
    that as "nothing trending", not an error.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        return []

    raw_ids = redis_client.zrevrange(trending_key(category), 0, limit - 1)
    return [int(raw_id) for raw_id in raw_ids]


def compute_personalized_recommendations() -> dict:
    """Recompute personalized recommendation scores for recently active users.

    For each user with a usage event in the trailing PERSONALIZED_LOOKBACK_DAYS, builds
    a facet profile from their most recent PERSONALIZED_HISTORY_LIMIT interactions, then
    scores the (still-visible) catalog against that profile using the same facet
    weights as compute_similar_recommendations, excluding assets already in the user's
    history. Intended to run nightly via Celery beat
    (compute_personalized_recommendations_task).

    Users with no scoreable candidates (e.g. their whole history is now
    unpublished/restricted) get their key deleted rather than left stale, matching
    compute_similar_recommendations. Users the endpoint has no precomputed data for
    (never scored, or scored to nothing) fall back to trending -- see
    get_personalized_asset_ids and the /recommendations/personalized/ endpoint.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        logger.warning("compute_personalized_recommendations: no Redis available, skipping")
        return {"users_scored": 0, "keys_written": 0}

    since = timezone.now() - timedelta(days=PERSONALIZED_LOOKBACK_DAYS)
    visible_assets = _visible_asset_values()
    by_reciter, by_riwayah, by_qiraah, by_category, asset_by_id = _build_facet_index(visible_assets)

    user_ids = list(
        UsageEvent.objects.filter(created_at__gte=since).values_list("developer_user_id", flat=True).distinct()
    )

    keys_written = 0
    with redis_client.pipeline() as pipe:
        for user_id in user_ids:
            key = personalized_key(user_id)
            pipe.delete(key)

            history_asset_ids = list(
                UsageEvent.objects.filter(developer_user_id=user_id, created_at__gte=since)
                .order_by("-created_at")
                .values_list("asset_id", flat=True)[:PERSONALIZED_HISTORY_LIMIT]
            )
            seen_ids = set(history_asset_ids)
            profile = [asset_by_id[aid] for aid in history_asset_ids if aid in asset_by_id]
            if not profile:
                continue

            candidate_scores = _score_profile_against_catalog(
                profile, seen_ids, by_reciter, by_riwayah, by_qiraah, by_category, asset_by_id
            )
            if not candidate_scores:
                continue

            top = sorted(candidate_scores.items(), key=lambda kv: kv[1], reverse=True)[:PERSONALIZED_TOP_N]
            pipe.zadd(key, {str(other_id): score for other_id, score in top})
            pipe.expire(key, PERSONALIZED_KEY_TTL_SECONDS)
            keys_written += 1
        pipe.execute()

    logger.info(f"compute_personalized_recommendations: scored {len(user_ids)} users, wrote {keys_written} keys")
    return {"users_scored": len(user_ids), "keys_written": keys_written}


def get_personalized_asset_ids(user_id: int, limit: int = PERSONALIZED_TOP_N) -> list[int]:
    """Read precomputed personalized asset ids for `user_id`, best match first.

    Returns an empty list when Redis is unavailable or no precomputed entry exists for
    this user -- the /recommendations/personalized/ endpoint treats that as "fall back
    to trending", not an error.
    """
    redis_client = get_recommendations_redis()
    if redis_client is None:
        return []

    raw_ids = redis_client.zrevrange(personalized_key(user_id), 0, limit - 1)
    return [int(raw_id) for raw_id in raw_ids]


def list_active_editorial_recommendations() -> list[dict]:
    """Admin-curated collections currently within their active window, newest first.

    Unlike similar/trending/personalized this reads straight from the DB: editorial
    collections change rarely (admin-curated, not per-request computed) and the query
    is already small and indexed, so there's no precompute/cache step.

    Each collection's assets are filtered to the same READY/public visibility as every
    other recommendation surface and ordered by their curated position. A collection
    that currently has no visible assets (e.g. everything in it got unpublished) is
    omitted entirely rather than served empty.
    """
    now = timezone.now()
    collections = (
        EditorialRecommendation.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .prefetch_related(
            "recommendation_assets__asset__publisher",
            "recommendation_assets__asset__reciter",
            "recommendation_assets__asset__riwayah",
        )
        .order_by("-created_at")
    )

    results = []
    for collection in collections:
        assets = [
            ra.asset
            for ra in collection.recommendation_assets.all()
            if ra.asset.status == StatusChoice.READY and not ra.asset.restricted_for_tenant
        ]
        if not assets:
            continue
        results.append(
            {
                "id": collection.id,
                "title": collection.title,
                "description": collection.description,
                "assets": assets,
            }
        )

    return results


__all__ = [
    "CategoryChoice",
    "PERSONALIZED_TOP_N",
    "SIMILAR_TOP_N",
    "TRENDING_TOP_N",
    "compute_personalized_recommendations",
    "compute_similar_recommendations",
    "compute_trending_recommendations",
    "get_personalized_asset_ids",
    "get_similar_asset_ids",
    "get_trending_asset_ids",
    "hydrate_visible_assets_in_order",
    "list_active_editorial_recommendations",
]
