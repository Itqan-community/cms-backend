from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag
from apps.personalization.services import history as history_service

router = ItqanRouter(tags=[NinjaTag.LISTENING_HISTORY])


# ── Schemas ─────────────────────────────────────────────────────


class HistoryRecordIn(Schema):
    asset_id: int
    surah_number: int | None = None
    position_ms: int = Field(..., ge=0, description="Current playback position in milliseconds")
    duration_ms: int = Field(0, ge=0, description="Duration listened in this session (milliseconds)")


class HistoryReciterOut(Schema):
    id: int
    name: str


class HistoryOut(Schema):
    id: int
    asset_id: int
    asset_name: str
    reciter: HistoryReciterOut | None
    surah_number: int | None
    last_position_ms: int
    duration_listened_ms: int
    played_at: AwareDatetime

    @staticmethod
    def resolve_asset_name(obj):
        return obj.asset.name if obj.asset else ""

    @staticmethod
    def resolve_reciter(obj):
        reciter = obj.asset.reciter if obj.asset else None
        if reciter:
            return {"id": reciter.id, "name": reciter.name}
        return None


# ── Endpoints ───────────────────────────────────────────────────


@router.post("history/", response={201: HistoryOut}, summary="Record playback")
def record_playback(request: Request, data: HistoryRecordIn):
    """
    Record or update a listening history entry.

    Uses upsert logic: if a history entry for the same user + asset + surah_number
    already exists, it updates the position and timestamp rather than creating a duplicate.
    """
    history = history_service.record_playback(
        user=request.user,
        asset_id=data.asset_id,
        position_ms=data.position_ms,
        surah_number=data.surah_number,
        duration_ms=data.duration_ms,
    )
    # Re-fetch with select_related for proper serialization
    from apps.personalization.models import ListeningHistory

    history = ListeningHistory.objects.select_related("asset", "asset__reciter").get(id=history.id)
    return 201, history


@router.get("history/", response=list[HistoryOut], summary="Get listening history")
@paginate
def get_history(request: Request):
    """
    Get the authenticated user's listening history, ordered by most recently played.
    Includes asset and reciter details for each entry.
    """
    return history_service.get_history(user=request.user)


@router.delete("history/", response=OkSchema, summary="Clear listening history")
def clear_history(request: Request):
    """
    Clear all listening history for the authenticated user.
    Returns the number of entries that were deleted.
    """
    count = history_service.clear_history(user=request.user)
    return {"message": f"Cleared {count} history entries."}
