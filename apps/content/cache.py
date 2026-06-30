from django.core.cache import cache

RECITATION_TRACKS_CACHE_TTL = 60 * 5  # 5 minutes


def recitation_tracks_cache_key(asset_id: int) -> str:
    return f"public_recitation_tracks:{asset_id}"


def invalidate_recitation_tracks_cache(asset_id: int) -> None:
    cache.delete(recitation_tracks_cache_key(asset_id))
