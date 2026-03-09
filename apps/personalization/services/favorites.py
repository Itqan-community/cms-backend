from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from apps.content.models import Asset, Reciter, Resource
from apps.core.ninja_utils.errors import ItqanError
from apps.personalization.models import Favorite

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User

# Map of allowed content type strings to their model classes
FAVORITE_CONTENT_TYPES = {
    "reciter": Reciter,
    "resource": Resource,
    "asset": Asset,
}


def _get_content_type(content_type_str: str) -> ContentType:
    """Resolve a content type string to a Django ContentType instance."""
    model_class = FAVORITE_CONTENT_TYPES.get(content_type_str)
    if not model_class:
        raise ItqanError(
            error_name="invalid_content_type",
            message=f"Invalid content type '{content_type_str}'. Must be one of: {', '.join(FAVORITE_CONTENT_TYPES.keys())}",
            status_code=400,
        )
    return ContentType.objects.get_for_model(model_class)


def _validate_object_exists(content_type_str: str, object_id: int) -> None:
    """Validate that the target object exists."""
    model_class = FAVORITE_CONTENT_TYPES[content_type_str]
    if not model_class.objects.filter(id=object_id).exists():
        raise ItqanError(
            error_name="object_not_found",
            message=f"{content_type_str.capitalize()} with ID {object_id} not found.",
            status_code=404,
        )


def toggle_favorite(user: User, content_type_str: str, object_id: int) -> dict:
    """
    Toggle a favorite. If already favorited, remove it. If not, create it.

    Returns:
        dict with 'action' ('added' or 'removed') and 'favorite_count'.
    """
    ct = _get_content_type(content_type_str)
    _validate_object_exists(content_type_str, object_id)

    existing = Favorite.objects.filter(user=user, content_type=ct, object_id=object_id)

    if existing.exists():
        existing.delete()
        action = "removed"
    else:
        Favorite.objects.create(user=user, content_type=ct, object_id=object_id)
        action = "added"

    favorite_count = Favorite.objects.filter(content_type=ct, object_id=object_id).count()

    return {"action": action, "favorite_count": favorite_count}


def list_user_favorites(user: User, content_type_str: str | None = None) -> QuerySet[Favorite]:
    """
    List all favorites for a user, optionally filtered by content type.
    """
    qs = Favorite.objects.filter(user=user).select_related("content_type").order_by("-created_at")

    if content_type_str:
        ct = _get_content_type(content_type_str)
        qs = qs.filter(content_type=ct)

    return qs


def is_favorited(user: User, content_type_str: str, object_id: int) -> bool:
    """Check if a user has favorited a specific object."""
    ct = _get_content_type(content_type_str)
    return Favorite.objects.filter(user=user, content_type=ct, object_id=object_id).exists()


def get_favorite_count(content_type_str: str, object_id: int) -> int:
    """Get total favorite count for an object (for social proof)."""
    ct = _get_content_type(content_type_str)
    return Favorite.objects.filter(content_type=ct, object_id=object_id).count()


def get_favorite_stats() -> dict:
    """Get aggregate favorite statistics for admin dashboard."""
    total = Favorite.objects.count()

    by_type = (
        Favorite.objects.values("content_type__model")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    top_items = (
        Favorite.objects.values("content_type__model", "object_id")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    return {
        "total_favorites": total,
        "by_content_type": {item["content_type__model"]: item["count"] for item in by_type},
        "top_favorited_items": list(top_items),
    }
