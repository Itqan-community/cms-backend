"""Dedicated Redis client + key helpers for the content recommendation engine.

Recommendation scores are precomputed nightly (see apps.content.tasks) and stored as
Redis sorted sets so reads at request time are O(log N) with no DB round trip. This
mirrors apps.usage_tracking.tasks' `_build_tracking_redis` pattern: reuse the `default`
django-redis connection's host/port/auth/TLS, but swap to a dedicated DB so recommendation
keys can't be evicted by the Django cache's eviction policy and don't collide with the
tracking buffer (DB 2).
"""

from __future__ import annotations

import redis

# Separate Redis DB from the Django cache (DB 1) and the usage-tracking buffer (DB 2).
_RECOMMENDATIONS_REDIS_DB = 3

# Sentinel distinguishing "not resolved yet" from a resolved-to-None client (no Redis,
# e.g. dev's LocMemCache), so we resolve at most once instead of on every call.
_UNSET = object()
_recommendations_redis_client: redis.Redis | None | object = _UNSET


def _build_recommendations_redis() -> redis.Redis | None:
    """Build the recommendations Redis client, or ``None`` when no Redis is available.

    Connection details reuse the ``default`` cache's django-redis connection (host, port,
    auth, TLS, socket opts), then swap to a dedicated DB.

    Returns ``None`` when the cache backend is not django-redis (e.g. dev's LocMemCache):
    callers treat that as "no precomputed recommendations available" and can fall back
    accordingly (e.g. personalized falling back to trending, or an empty result).
    """
    try:
        from django_redis import get_redis_connection

        cache_conn = get_redis_connection("default")
    except (ImportError, NotImplementedError):
        # ImportError: django-redis absent. NotImplementedError: get_redis_connection on a
        # non-django-redis backend (LocMemCache in dev). Either way, no Redis to reuse.
        return None

    kwargs = dict(cache_conn.connection_pool.connection_kwargs)
    kwargs["db"] = _RECOMMENDATIONS_REDIS_DB
    kwargs.setdefault("socket_connect_timeout", 1)
    kwargs.setdefault("socket_timeout", 1)
    kwargs["decode_responses"] = True
    return redis.Redis(**kwargs)


def get_recommendations_redis() -> redis.Redis | None:
    """Return the module-level recommendations Redis client, or ``None`` when unavailable.

    Lazy-initialised (settings must be loaded) and resolved once; see
    :func:`_build_recommendations_redis` for how the connection is derived.
    """
    global _recommendations_redis_client
    if _recommendations_redis_client is _UNSET:
        _recommendations_redis_client = _build_recommendations_redis()
    return _recommendations_redis_client


def reset_recommendations_redis_cache() -> None:
    """Clear the memoized client so tests can force a fresh resolution."""
    global _recommendations_redis_client
    _recommendations_redis_client = _UNSET


# --- key helpers -------------------------------------------------------------------


def similar_key(asset_id: int) -> str:
    return f"recommendations:similar:{asset_id}"


def trending_key(category: str | None = None) -> str:
    return f"recommendations:trending:{category}" if category else "recommendations:trending:global"


def personalized_key(user_id: int) -> str:
    return f"recommendations:personalized:{user_id}"
