from ninja import Schema

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.personalization.services import favorites as favorites_service

router = ItqanRouter(tags=[NinjaTag.FAVORITES])


# ── Schemas ─────────────────────────────────────────────────────


class FavoriteStatsOut(Schema):
    total_favorites: int
    by_content_type: dict[str, int]
    top_favorited_items: list[dict]


# ── Endpoints ───────────────────────────────────────────────────


@router.get(
    "favorites/stats/",
    response=FavoriteStatsOut,
    auth=ninja_jwt_auth,
    summary="Get favorite statistics",
)
def get_favorite_stats(request: Request):
    """
    Get aggregate statistics about favorites across the platform.
    Staff-only endpoint for the CMS dashboard.

    Returns:
    - Total number of favorites
    - Breakdown by content type (reciter, resource, asset)
    - Top 10 most favorited items
    """
    return favorites_service.get_favorite_stats()
