from django.shortcuts import get_object_or_404
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, RecitationSurahTrack, Resource
from apps.core.mixins.constants import QURAN_SURAHS
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
    def resolve_surah_name_en(obj: RecitationSurahTrack):
        return QURAN_SURAHS[obj.surah_number]["name_en"]


@router.get("recitation-tracks/{asset_id}/", response=list[RecitationSurahTrackOut])
@paginate
def list_recitation_tracks(request: Request, asset_id: int):
    asset = get_object_or_404(
        Asset.objects.filter(
            id=asset_id,
            category=Asset.CategoryChoice.RECITATION,
            resource__category=Resource.CategoryChoice.RECITATION,
            resource__status=Resource.StatusChoice.READY,
        )
    )

    tracks = RecitationSurahTrack.objects.filter(asset=asset).order_by("surah_number")

    return tracks
