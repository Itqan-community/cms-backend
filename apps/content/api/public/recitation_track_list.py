from typing import Literal

from django.core.cache import cache
from django.db.models import Q
from django.http import Http404
from ninja import Schema
from ninja.pagination import paginate

from apps.content.cache import RECITATION_TRACKS_CACHE_TTL, recitation_tracks_cache_key
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.paginations import PublicRecitationPagination
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage
from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationAyahTimingOut(Schema):
    ayah_key: str
    start_ms: int
    end_ms: int
    duration_ms: int


class RecitationSurahTrackOut(Schema):
    surah_number: int
    surah_name: str
    surah_name_en: str
    audio_url: str
    duration_ms: int
    size_bytes: int
    revelation_order: int
    revelation_place: Literal["Makkah", "Madinah"]
    ayahs_count: int
    ayahs_timings: list[RecitationAyahTimingOut]


@router.get(
    "recitations/{asset_id}/",
    response={200: list[RecitationSurahTrackOut], 404: NinjaErrorResponse[Literal["not_found"]]},
)
@track_usage()
@paginate(PublicRecitationPagination)
def list_recitation_tracks(request: Request, asset_id: int):
    repo = RecitationRepository()
    service = RecitationService(repo)

    # Public API doesn't filter by publisher by default
    asset = repo.get_asset_object(asset_id, Q())
    if not asset:
        # 404s raise before track_extra, so the decorator dispatches nothing for them.
        raise Http404("No asset matches the given query.")

    # Publisher is a property of the served Asset (select_related in get_asset_object).
    track_extra(
        request,
        entity_type="recitation",
        accessed_entity_name=asset.name,
        entity_ids=[asset.id],
        entity_names=[asset.name],
        publisher_ids=[asset.publisher_id] if asset.publisher_id else [],
        publisher_names=[asset.publisher.name] if asset.publisher_id else [],
    )

    # Cache the full track list per asset. The paginator slices from this list,
    # so 144 concurrent devices all hitting the same asset pay the DB cost once.
    _cache_key = recitation_tracks_cache_key(asset_id)
    cached: list[RecitationSurahTrackOut] | None = cache.get(_cache_key)
    if cached is not None:
        return cached

    tracks = service.get_asset_tracks(asset_id, Q(), prefetch_timings=True)

    results: list[RecitationSurahTrackOut] = []

    for track in tracks:
        audio_url = f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{track.audio_file.name}"

        ayah_timings: list[RecitationAyahTimingOut] = []
        sorted_ayah_timings_qs = sorted(
            track.ayah_timings.all(),
            key=lambda a: (int(a.ayah_key.split(":")[0]), int(a.ayah_key.split(":")[1])),
        )
        for t in sorted_ayah_timings_qs:
            ayah_timings.append(
                RecitationAyahTimingOut(
                    ayah_key=t.ayah_key,
                    start_ms=t.start_ms,
                    end_ms=t.end_ms,
                    duration_ms=t.duration_ms,
                )
            )

        results.append(
            RecitationSurahTrackOut(
                surah_number=track.surah_number,
                surah_name=QURAN_SURAHS[track.surah_number]["name"],
                surah_name_en=QURAN_SURAHS[track.surah_number]["name_en"],
                audio_url=audio_url,
                duration_ms=track.duration_ms,
                size_bytes=track.size_bytes,
                revelation_order=QURAN_SURAHS[track.surah_number]["revelation_order"],
                revelation_place=QURAN_SURAHS[track.surah_number]["revelation_place"],
                ayahs_count=QURAN_SURAHS[track.surah_number]["ayahs_count"],
                ayahs_timings=ayah_timings,
            )
        )

    cache.set(_cache_key, results, RECITATION_TRACKS_CACHE_TTL)
    return results
