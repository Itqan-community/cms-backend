from typing import Literal

from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag
from apps.personalization.services import favorites as favorites_service

router = ItqanRouter(tags=[NinjaTag.FAVORITES])


# ── Schemas ─────────────────────────────────────────────────────


class FavoriteToggleIn(Schema):
    content_type: Literal["reciter", "resource", "asset"]
    object_id: int


class FavoriteToggleOut(Schema):
    action: Literal["added", "removed"]
    favorite_count: int


class FavoriteOut(Schema):
    id: int
    content_type: str
    object_id: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_content_type(obj):
        return obj.content_type.model


class FavoriteFilter(FilterSchema):
    content_type: Literal["reciter", "resource", "asset"] | None = Field(
        None, description="Filter by content type"
    )


# ── Endpoints ───────────────────────────────────────────────────


@router.post(
    "favorites/toggle/",
    response={200: FavoriteToggleOut, 201: FavoriteToggleOut},
    summary="Toggle favorite on/off",
)
def toggle_favorite(request: Request, data: FavoriteToggleIn):
    """
    Toggle a favorite on a Reciter, Resource, or Asset.

    - If the item is already favorited → removes the favorite (200)
    - If the item is not yet favorited → creates the favorite (201)

    Returns the action performed and the updated favorite count for social proof.
    """
    result = favorites_service.toggle_favorite(
        user=request.user,
        content_type_str=data.content_type,
        object_id=data.object_id,
    )

    status_code = 201 if result["action"] == "added" else 200
    return status_code, result


@router.get("favorites/", response=list[FavoriteOut], summary="List user favorites")
@paginate
def list_favorites(request: Request, filters: FavoriteFilter = Query()):
    """
    List all favorites for the authenticated user.
    Optionally filter by content type (reciter, resource, asset).
    """
    content_type_str = None
    if filters and hasattr(filters, "content_type") and filters.content_type:
        content_type_str = filters.content_type

    return favorites_service.list_user_favorites(
        user=request.user,
        content_type_str=content_type_str,
    )
