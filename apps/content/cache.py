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
    cache.delete_many(
        [
            recitation_tracks_cache_key(asset_id),
            recitation_asset_meta_cache_key(asset_id),
        ]
    )
    # Also wipe pre-serialized response keys for this asset (page/page_size vary, use pattern).
    try:
        cache.delete_pattern(f"*:public_recitation_resp:{asset_id}:*")
    except AttributeError:
        pass  # non-Redis backend (e.g. locmem in tests)
