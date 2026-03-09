from __future__ import annotations

from typing import TYPE_CHECKING

from apps.content.models import Asset
from apps.core.ninja_utils.errors import ItqanError
from apps.personalization.models import Bookmark

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


def _validate_asset_exists(asset_id: int) -> Asset:
    """Validate that the asset exists and return it."""
    try:
        return Asset.objects.get(id=asset_id)
    except Asset.DoesNotExist:
        raise ItqanError(
            error_name="asset_not_found",
            message=f"Asset with ID {asset_id} not found.",
            status_code=404,
        )


def create_bookmark(
    user: User,
    asset_id: int,
    position_ms: int,
    surah_number: int | None = None,
    note: str = "",
) -> Bookmark:
    """
    Create a new bookmark for the user on the given asset.
    """
    _validate_asset_exists(asset_id)

    if note and len(note) > 500:
        raise ItqanError(
            error_name="validation_error",
            message="Note cannot exceed 500 characters.",
            status_code=400,
        )

    bookmark = Bookmark.objects.create(
        user=user,
        asset_id=asset_id,
        surah_number=surah_number,
        position_ms=position_ms,
        note=note or "",
    )

    return bookmark


def list_bookmarks(user: User) -> QuerySet[Bookmark]:
    """
    List all bookmarks for a user, ordered by most recent first.
    Uses select_related to avoid N+1 queries on asset and its reciter.
    """
    return (
        Bookmark.objects.filter(user=user)
        .select_related("asset", "asset__reciter")
        .order_by("-created_at")
    )


def delete_bookmark(user: User, bookmark_id: int) -> None:
    """
    Delete a bookmark, ensuring the user owns it.
    """
    try:
        bookmark = Bookmark.objects.get(id=bookmark_id, user=user)
    except Bookmark.DoesNotExist:
        raise ItqanError(
            error_name="bookmark_not_found",
            message=f"Bookmark with ID {bookmark_id} not found.",
            status_code=404,
        )

    bookmark.delete()
