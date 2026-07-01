from django.core.cache import cache

RECITATION_TRACKS_CACHE_TTL = 60 * 5  # 5 minutes
RECITATION_ASSET_META_CACHE_TTL = 60 * 60  # 1 hour - asset name/publisher rarely changes


def recitation_tracks_cache_key(asset_id: int) -> str:
    return f"public_recitation_tracks:{asset_id}"


def recitation_asset_meta_cache_key(asset_id: int) -> str:
    return f"public_recitation_asset_meta:{asset_id}"


def invalidate_recitation_tracks_cache(asset_id: int) -> None:
    cache.delete_many([recitation_tracks_cache_key(asset_id), recitation_asset_meta_cache_key(asset_id)])
