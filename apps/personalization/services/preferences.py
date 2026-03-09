from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.personalization.models import UserPreference

if TYPE_CHECKING:
    from apps.users.models import User

# Default notification settings for new preferences
DEFAULT_NOTIFICATION_SETTINGS = {
    "new_content": True,
    "recommendations": True,
}


def get_or_create_preferences(user: User) -> UserPreference:
    """
    Get existing preferences or create with defaults.
    Uses get_or_create for atomic operation.
    """
    preference, _created = UserPreference.objects.get_or_create(
        user=user,
        defaults={
            "preferred_reciter_ids": [],
            "preferred_qiraah_ids": [],
            "preferred_riwayah_ids": [],
            "audio_quality": UserPreference.AudioQualityChoice.HIGH,
            "language": "en",
            "notification_settings": DEFAULT_NOTIFICATION_SETTINGS,
        },
    )
    return preference


def update_preferences(user: User, data: dict[str, Any]) -> UserPreference:
    """
    Partial update of user preferences. Only updates fields that are provided.
    Creates the preference if it doesn't exist yet.
    """
    preference = get_or_create_preferences(user)

    # Only update fields that are explicitly provided (not None)
    updatable_fields = [
        "preferred_reciter_ids",
        "preferred_qiraah_ids",
        "preferred_riwayah_ids",
        "audio_quality",
        "language",
        "notification_settings",
    ]

    update_fields = []
    for field in updatable_fields:
        if field in data and data[field] is not None:
            setattr(preference, field, data[field])
            update_fields.append(field)

    if update_fields:
        update_fields.append("updated_at")
        preference.save(update_fields=update_fields)

    return preference
