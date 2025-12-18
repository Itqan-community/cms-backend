from django.shortcuts import get_object_or_404
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, RecitationSurahTrack, Resource
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationSurahTrackOut(Schema):
    surah_number: int
    surah_name: str
    surah_name_ar: str
    chapter_number: int | None = None
    audio_url: str | None = Field(
        None,
        description="Absolute URL to the per-surah audio file (MP3)",
    )
    duration_ms: int
    size_bytes: int


@router.get(
    "recitations/{asset_id}/",
    response=list[RecitationSurahTrackOut],
    auth=None,
)
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

    results: list[RecitationSurahTrackOut] = []

    for track in tracks:
        if track.audio_file:
            audio_url = request.build_absolute_uri(track.audio_file.url)
        else:
            audio_url = None

        results.append(
            RecitationSurahTrackOut(
                surah_number=track.surah_number,
                surah_name=track.surah_name,
                surah_name_ar=track.surah_name_ar,
                chapter_number=track.chapter_number,
                audio_url=audio_url,
                duration_ms=track.duration_ms,
                size_bytes=track.size_bytes,
            )
        )

    return results
