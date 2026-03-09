from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag
from apps.personalization.services import bookmarks as bookmarks_service

router = ItqanRouter(tags=[NinjaTag.BOOKMARKS])


# ── Schemas ─────────────────────────────────────────────────────


class BookmarkIn(Schema):
    asset_id: int
    surah_number: int | None = None
    position_ms: int = Field(..., ge=0, description="Playback position in milliseconds")
    note: str | None = Field(None, max_length=500, description="Optional note")


class BookmarkOut(Schema):
    id: int
    asset_id: int
    asset_name: str
    surah_number: int | None
    position_ms: int
    note: str
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @staticmethod
    def resolve_asset_name(obj):
        return obj.asset.name if obj.asset else ""


# ── Endpoints ───────────────────────────────────────────────────


@router.post("bookmarks/", response={201: BookmarkOut}, summary="Create a bookmark")
def create_bookmark(request: Request, data: BookmarkIn):
    """
    Create a new bookmark on an audio asset with a playback position in milliseconds.
    This allows audio playback to resume exactly where it stopped.
    """
    bookmark = bookmarks_service.create_bookmark(
        user=request.user,
        asset_id=data.asset_id,
        position_ms=data.position_ms,
        surah_number=data.surah_number,
        note=data.note or "",
    )
    # Re-fetch with select_related for proper serialization
    from apps.personalization.models import Bookmark

    bookmark = Bookmark.objects.select_related("asset").get(id=bookmark.id)
    return 201, bookmark


@router.get("bookmarks/", response=list[BookmarkOut], summary="List user bookmarks")
@paginate
def list_bookmarks(request: Request):
    """
    List all bookmarks for the authenticated user, ordered by most recent first.
    Includes asset details for each bookmark.
    """
    return bookmarks_service.list_bookmarks(user=request.user)


@router.delete("bookmarks/{bookmark_id}/", response=OkSchema, summary="Delete a bookmark")
def delete_bookmark(request: Request, bookmark_id: int):
    """
    Delete a specific bookmark. Only the bookmark owner can delete it.
    """
    bookmarks_service.delete_bookmark(user=request.user, bookmark_id=bookmark_id)
    return {"message": "Bookmark deleted successfully."}
