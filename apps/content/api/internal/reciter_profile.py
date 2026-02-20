"""
Reciter profile endpoint.

GET /cms-api/reciters/<reciter_id>/
Returns reciter info with nested recitations and their tracks.
"""

from typing import Literal

from django.http import Http404

from ninja import Schema
from pydantic import Field

from apps.content.models import Asset, RecitationSurahTrack
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITERS])


# ── Response Schemas ────────────────────────────────────────────────


class TrackOut(Schema):
    """Minimal track representation nested inside a recitation."""

    surah_number: int
    surah_name: str
    surah_name_en: str
    audio_url: AbsoluteUrl = Field(alias="audio_file")
    duration_ms: int
    size_bytes: int

    @staticmethod
    def resolve_surah_name(obj: RecitationSurahTrack) -> str:
        return QURAN_SURAHS[obj.surah_number]["name"]

    @staticmethod
    def resolve_surah_name_en(obj: RecitationSurahTrack) -> str:
        return QURAN_SURAHS[obj.surah_number]["name_en"]


class RiwayahOut(Schema):
    id: int
    name: str


class QiraahOut(Schema):
    id: int
    name: str


class RecitationOut(Schema):
    """A single recitation (Asset) belonging to the reciter."""

    id: int
    name: str
    description: str
    recitation_type: Asset.RecitationTypeChoice | None
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviorChoice | None
    year: int | None
    format: str
    riwayah: RiwayahOut | None
    qiraah: QiraahOut | None
    tracks: list[TrackOut]

    @staticmethod
    def resolve_tracks(obj: Asset) -> list:
        # Uses prefetch_related("recitation_tracks") from the queryset
        return list(obj.recitation_tracks.all())



class ReciterProfileOut(Schema):
    """Full reciter profile with nested recitations."""

    id: int
    name: str
    bio: str
    image_url: AbsoluteUrl | None
    recitations: list[RecitationOut]


# ── Endpoint ────────────────────────────────────────────────────────


@router.get(
    "reciters/{reciter_id}/",
    response={200: ReciterProfileOut, 404: NinjaErrorResponse[Literal["not_found"], Literal[None]]},
)
def reciter_profile(request: Request, reciter_id: int):
    """
    Returns full reciter profile including all READY recitations and their tracks.

    Optimised with `select_related` / `prefetch_related` to avoid N+1.
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    # Fetch reciter
    reciter = service.get_reciter(reciter_id)
    if not reciter:
        raise Http404("No reciter matches the given query.")

    # Fetch recitations with tracks (prefetched)
    publisher_q = request.publisher_q("resource__publisher")
    recitations = service.get_reciter_recitations(reciter, publisher_q)

    # Attach as attribute for the schema resolver
    reciter.recitations = list(recitations)  # type: ignore[attr-defined]

    return reciter
