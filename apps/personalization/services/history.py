from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.content.models import Asset
from apps.core.ninja_utils.errors import ItqanError
from apps.personalization.models import ListeningHistory

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.users.models import User


def record_playback(
    user: User,
    asset_id: int,
    position_ms: int,
    surah_number: int | None = None,
    duration_ms: int = 0,
) -> ListeningHistory:
    """
    Record or update a listening history entry.

    Uses update_or_create with (user, asset, surah_number) as the unique key.
    If a matching entry exists, it updates the position, duration, and timestamp.
    """
    if not Asset.objects.filter(id=asset_id).exists():
        raise ItqanError(
            error_name="asset_not_found",
            message=f"Asset with ID {asset_id} not found.",
            status_code=404,
        )

    history, _created = ListeningHistory.objects.update_or_create(
        user=user,
        asset_id=asset_id,
        surah_number=surah_number,
        defaults={
            "last_position_ms": position_ms,
            "duration_listened_ms": duration_ms,
            "played_at": timezone.now(),
        },
    )

    return history


def get_history(user: User) -> QuerySet[ListeningHistory]:
    """
    Get user's listening history ordered by most recent playback.
    Uses select_related to avoid N+1 on asset and reciter lookups.
    """
    return (
        ListeningHistory.objects.filter(user=user)
        .select_related("asset", "asset__reciter")
        .order_by("-played_at")
    )


def clear_history(user: User) -> int:
    """
    Clear all listening history for a user.
    Returns the number of entries deleted.
    """
    count, _ = ListeningHistory.objects.filter(user=user).delete()
    return count
