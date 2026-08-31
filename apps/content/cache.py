import hashlib
import re

from django.core.cache import cache

from apps.core.ninja_utils.paginations import DEFAULT_PAGE_SIZE, PUBLIC_RECITATION_MAX_PAGE_SIZE

# Stands in for "caller did not name a folder" in cache keys, so the default-folder
# response gets its own entry without a DB lookup to resolve the real slug.
DEFAULT_FOLDER_CACHE_TOKEN = "__default__"

# Slug-shaped tokens are safe to embed in a cache key verbatim; see folder_cache_token.
_SAFE_CACHE_TOKEN_RE = re.compile(r"^[a-z0-9_.-]{1,64}$")

RECITATION_TRACKS_CACHE_TTL = 60 * 5  # 5 minutes
RECITATION_ASSET_META_CACHE_TTL = 60 * 60  # 1 hour - asset name/publisher rarely changes
RECITATION_RESPONSE_CACHE_TTL = 60 * 5  # 5 minutes


def recitation_tracks_cache_key(asset_id: int) -> str:
    return f"public_recitation_tracks:{asset_id}"


def recitation_asset_meta_cache_key(asset_id: int) -> str:
    return f"public_recitation_asset_meta:{asset_id}"


def folder_cache_token(folder: str | None) -> str:
    """
    Turn a raw ``?folder=`` value into a safe, stable cache-key component.

    The value is user input and may be a folder *name*, so it can carry spaces,
    Arabic, or arbitrary length -- none of which belong in a cache key (memcached
    rejects such keys outright, and Django warns on every request under any backend).

    Slug-shaped values pass through unchanged so keys stay readable in Redis;
    anything else is hashed. Case is folded first because folder-name matching is
    case-insensitive: "With echo" and "WITH ECHO" resolve to the same folder and so
    must share one cache entry rather than duplicating it.
    """
    if folder is None:
        return DEFAULT_FOLDER_CACHE_TOKEN

    normalized = folder.strip().casefold()
    if _SAFE_CACHE_TOKEN_RE.match(normalized):
        return normalized
    return hashlib.blake2b(normalized.encode("utf-8"), digest_size=8).hexdigest()


def recitation_response_cache_key(asset_id: int, page: int, page_size: int, folder_slug: str) -> str:
    # The folder is part of the key: two variants of the same recitation share an
    # asset_id, so omitting it would serve one variant's audio for the other.
    return f"public_recitation_resp:{asset_id}:{folder_slug}:{page}:{page_size}"


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


def invalidate_recitation_folder_cache(asset_id: int, folder) -> None:
    """
    Bust public recitation caches after a folder's visibility or default status changes.

    Per-folder response keys for every page size cannot be enumerated cheaply, so the
    asset meta key is cleared to force rebuilds; known folder tokens are deleted when
    present so the common first-page case is immediate.
    """
    invalidate_recitation_tracks_cache(asset_id)

    tokens = {folder.slug, folder_cache_token(folder.slug)}
    for name in (folder.name, folder.name_ar, folder.name_en):
        if name:
            tokens.add(folder_cache_token(name))

    for token in tokens:
        for page in (1,):
            for page_size in (DEFAULT_PAGE_SIZE, PUBLIC_RECITATION_MAX_PAGE_SIZE):
                cache.delete(recitation_response_cache_key(asset_id, page, page_size, token))
