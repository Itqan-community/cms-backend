from typing import Literal

from ninja import Schema
from pydantic import AwareDatetime

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.personalization.services import preferences as preferences_service

router = ItqanRouter(tags=[NinjaTag.PREFERENCES])


# ── Schemas ─────────────────────────────────────────────────────


class NotificationSettingsSchema(Schema):
    new_content: bool = True
    recommendations: bool = True


class PreferenceIn(Schema):
    preferred_reciter_ids: list[int] | None = None
    preferred_qiraah_ids: list[int] | None = None
    preferred_riwayah_ids: list[int] | None = None
    audio_quality: Literal["low", "medium", "high"] | None = None
    language: str | None = None
    notification_settings: NotificationSettingsSchema | None = None


class PreferenceOut(Schema):
    preferred_reciter_ids: list[int]
    preferred_qiraah_ids: list[int]
    preferred_riwayah_ids: list[int]
    audio_quality: str
    language: str
    notification_settings: dict
    updated_at: AwareDatetime


# ── Endpoints ───────────────────────────────────────────────────


@router.get("preferences/", response=PreferenceOut, summary="Get user preferences")
def get_preferences(request: Request):
    """
    Get the authenticated user's preferences.
    If no preferences exist yet, returns defaults.
    """
    return preferences_service.get_or_create_preferences(user=request.user)


@router.put("preferences/", response=PreferenceOut, summary="Update user preferences")
def update_preferences(request: Request, data: PreferenceIn):
    """
    Update the authenticated user's preferences.
    Supports partial updates — only provided fields are changed.

    Available settings:
    - **preferred_reciter_ids**: List of Reciter IDs
    - **preferred_qiraah_ids**: List of Qiraah IDs
    - **preferred_riwayah_ids**: List of Riwayah IDs
    - **audio_quality**: low, medium, or high
    - **language**: Language code (e.g. 'en', 'ar')
    - **notification_settings**: Notification preferences
    """
    # Convert Pydantic model to dict, excluding None values
    update_data = data.dict(exclude_none=True)

    # Convert NotificationSettingsSchema to dict if present
    if "notification_settings" in update_data and hasattr(update_data["notification_settings"], "dict"):
        update_data["notification_settings"] = update_data["notification_settings"].dict()

    return preferences_service.update_preferences(user=request.user, data=update_data)
