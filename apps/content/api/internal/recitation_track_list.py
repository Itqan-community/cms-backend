from typing import Literal

from django.db.models import Q
from django.http import Http404
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import RecitationSurahTrack
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class ReciterOut(Schema):
    id: int
    name: str
    image_url: AbsoluteUrl | None
    bio: str


class RecitationSurahTrackOut(Schema):
    surah_number: int
    surah_name: str
    surah_name_en: str
    audio_url: AbsoluteUrl = Field(alias="audio_file")
    duration_ms: int
    size_bytes: int
    reciter: ReciterOut = Field(alias="asset.reciter")

    @staticmethod
    def resolve_surah_name(obj: RecitationSurahTrack):
        return QURAN_SURAHS[obj.surah_number]["name"]

    @staticmethod
    def resolve_surah_name_en(obj: RecitationSurahTrack) -> str:
        return QURAN_SURAHS[obj.surah_number]["name_en"]


@router.get(
    "recitation-tracks/{asset_id}/",
    response={200: list[RecitationSurahTrackOut], 404: NinjaErrorResponse[Literal["not_found"]]},
)
@paginate
def list_recitation_tracks(request: Request, asset_id: int):
    repo = RecitationRepository()
    service = RecitationService(repo)

    asset_publisher_q = request.publisher_q("publisher") & Q(restricted_for_tenant=False)

    asset = repo.get_asset_object(asset_id, asset_publisher_q)
    if not asset:
        raise Http404("No asset matches the given query.")

    track_publisher_q = request.publisher_q("publisher") & Q(asset__restricted_for_tenant=False)
    tracks = service.get_asset_tracks(asset_id, track_publisher_q)

    return tracks
