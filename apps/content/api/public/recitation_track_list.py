import json
from typing import Literal

from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from ninja import Query, Schema

from apps.content.cache import (
    RECITATION_ASSET_META_CACHE_TTL,
    RECITATION_RESPONSE_CACHE_TTL,
    recitation_asset_meta_cache_key,
    recitation_response_cache_key,
)
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.paginations import DEFAULT_PAGE_SIZE, PUBLIC_RECITATION_MAX_PAGE_SIZE
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
def list_recitation_tracks(
    request: Request,
    asset_id: int,
    page: int = Query(1, ge=1, le=114),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
):
    page_size = min(page_size, PUBLIC_RECITATION_MAX_PAGE_SIZE)

    _resp_key = recitation_response_cache_key(asset_id, page, page_size)
    _meta_key = recitation_asset_meta_cache_key(asset_id)

    cached_resp: bytes | None = cache.get(_resp_key)
    cached_meta: dict | None = cache.get(_meta_key)

    if cached_resp is not None and cached_meta is not None:
        track_extra(
            request,
            entity_type="recitation",
            accessed_entity_name=cached_meta["name"],
            entity_ids=[asset_id],
            entity_names=[cached_meta["name"]],
            publisher_ids=[cached_meta["publisher_id"]] if cached_meta["publisher_id"] else [],
            publisher_names=[cached_meta["publisher_name"]] if cached_meta["publisher_id"] else [],
        )
        resp = HttpResponse(cached_resp, content_type="application/json")
        resp["Cache-Control"] = "public, max-age=300, s-maxage=300"
        return resp

    # Cache miss - hit DB.
    repo = RecitationRepository()
    service = RecitationService(repo)

    asset = repo.get_asset_object(asset_id, Q())
    if not asset:
        raise Http404("No asset matches the given query.")

    publisher_name = asset.publisher.name if asset.publisher_id else None
    asset_meta = {
        "name": asset.name,
        "publisher_id": asset.publisher_id,
        "publisher_name": publisher_name,
    }

    track_extra(
        request,
        entity_type="recitation",
        accessed_entity_name=asset.name,
        entity_ids=[asset.id],
        entity_names=[asset.name],
        publisher_ids=[asset.publisher_id] if asset.publisher_id else [],
        publisher_names=[publisher_name] if asset.publisher_id else [],
    )

    tracks = service.get_asset_tracks(asset_id, Q(), prefetch_timings=True)

    all_results = []
    for track in tracks:
        audio_url = f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{track.audio_file.name}"
        surah = QURAN_SURAHS[track.surah_number]
        sorted_timings = sorted(
            track.ayah_timings.all(),
            key=lambda a: (int(a.ayah_key.split(":")[0]), int(a.ayah_key.split(":")[1])),
        )
        all_results.append(
            {
                "surah_number": track.surah_number,
                "surah_name": surah["name"],
                "surah_name_en": surah["name_en"],
                "audio_url": audio_url,
                "duration_ms": track.duration_ms,
                "size_bytes": track.size_bytes,
                "revelation_order": surah["revelation_order"],
                "revelation_place": surah["revelation_place"],
                "ayahs_count": surah["ayahs_count"],
                "ayahs_timings": [
                    {
                        "ayah_key": t.ayah_key,
                        "start_ms": t.start_ms,
                        "end_ms": t.end_ms,
                        "duration_ms": t.duration_ms,
                    }
                    for t in sorted_timings
                ],
            }
        )

    total = len(all_results)
    offset = (page - 1) * page_size
    paginated = all_results[offset : offset + page_size]

    response_bytes = json.dumps({"results": paginated, "count": total}).encode()

    if offset < total:
        # Only cache pages that have content; out-of-range pages are not worth storing.
        cache.set(_resp_key, response_bytes, RECITATION_RESPONSE_CACHE_TTL)
    cache.set(_meta_key, asset_meta, RECITATION_ASSET_META_CACHE_TTL)

    resp = HttpResponse(response_bytes, content_type="application/json")
    resp["Cache-Control"] = "public, max-age=300, s-maxage=300"
    return resp
