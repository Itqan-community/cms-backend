from django.core.cache import cache

RECITATION_TRACKS_CACHE_TTL = 60 * 5  # 5 minutes
RECITATION_ASSET_META_CACHE_TTL = 60 * 60  # 1 hour - asset name/publisher rarely changes
RECITATION_RESPONSE_CACHE_TTL = 60 * 5  # 5 minutes


def recitation_tracks_cache_key(asset_id: int) -> str:
    return f"public_recitation_tracks:{asset_id}"


def recitation_asset_meta_cache_key(asset_id: int) -> str:
    return f"public_recitation_asset_meta:{asset_id}"


def recitation_response_cache_key(asset_id: int, page: int, page_size: int) -> str:
    return f"public_recitation_resp:{asset_id}:{page}:{page_size}"


def invalidate_recitation_tracks_cache(asset_id: int) -> None:
    # Deleting meta is sufficient: the view requires both resp AND meta for a cache hit,
    # so clearing meta forces a full DB rebuild on the next request. Stale resp bytes
    # for any (page, page_size) variant are overwritten on that rebuild and expire
    # naturally within RECITATION_RESPONSE_CACHE_TTL (5 min) for untouched variants.
    cache.delete_many(
        [
            recitation_tracks_cache_key(asset_id),
            recitation_asset_meta_cache_key(asset_id),
        ]
    )
