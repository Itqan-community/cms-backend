import json
from typing import Literal

from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils.translation import gettext_lazy as _
from ninja import Query, Schema

from apps.content.cache import (
    RECITATION_ASSET_META_CACHE_TTL,
    RECITATION_RESPONSE_CACHE_TTL,
    folder_cache_token,
    recitation_asset_meta_cache_key,
    recitation_range_cache_key,
)
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.asset_access import enforce_asset_access_on_public_api
from apps.content.services.recitation import RecitationService
from apps.content.services.recitation_range import RecitationRangeService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RangeAyahTimingOut(Schema):
    # One ayah inside the combined clip: absolute offsets in the source surah
    # file plus offset_ms relative to the clip start (0-based) for players.
    ayah_key: str
    start_ms: int
    end_ms: int
    duration_ms: int
    offset_ms: int


class RecitationRangeOut(Schema):
    # Combined audio for a contiguous ayah range: served as JSON + R2 URL so
    # the clip itself stays CDN-cacheable and repeats never re-encode.
    # Query params use ?from=&to= (aliased on input); the response exposes
    # plain from_ayah/to_ayah keys to avoid alias-serialization surprises.
    asset_id: int
    surah_number: int
    from_ayah: int
    to_ayah: int
    folder: str
    audio_url: str
    duration_ms: int
    size_bytes: int
    ayahs_timings: list[RangeAyahTimingOut]


@router.get(
    "recitations/{asset_id}/{surah_number}/range/",
    response={
        200: RecitationRangeOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["not_found"]] | NinjaErrorResponse[Literal["folder_not_found"]],
        422: NinjaErrorResponse[Literal["validation_error"]],
    },
)
@track_usage()
def get_recitation_range(
    request: Request,
    asset_id: int,
    surah_number: int,
    from_ayah: int = Query(..., alias="from", ge=1),
    to_ayah: int = Query(..., alias="to", ge=1),
    folder: str | None = Query(None),
):
    # Key on the *requested* folder (not the resolved one) so the warm path
    # needs no DB read; folder_cache_token keeps raw names safe in the key.
    # "from" is a Python keyword, hence the from_ayah alias above.
    _resp_key = recitation_range_cache_key(asset_id, surah_number, from_ayah, to_ayah, folder_cache_token(folder))
    _meta_key = recitation_asset_meta_cache_key(asset_id)

    cached_resp: bytes | None = cache.get(_resp_key)
    cached_meta: dict | None = cache.get(_meta_key)

    if cached_resp is not None and cached_meta is not None and "is_open_access" in cached_meta:
        # Warm path: enforce access from cached metadata (no DB query), then
        # attribute usage before returning the pre-serialized JSON bytes.
        is_open_access: bool = cached_meta["is_open_access"]
        if not is_open_access:
            enforce_asset_access_on_public_api(
                getattr(request, "user", None),
                asset_id=asset_id,
                is_open_access=is_open_access,
            )

        track_extra(
            request,
            entity_type="recitation_range",
            accessed_entity_name=cached_meta["name_ar"],
            entity_ids=[asset_id],
            entity_names=[cached_meta["name_ar"]],
            publisher_ids=[cached_meta["publisher_id"]] if cached_meta["publisher_id"] else [],
            publisher_names=[cached_meta["publisher_name"]] if cached_meta["publisher_id"] else [],
            surah_number=surah_number,
            from_ayah=from_ayah,
            to_ayah=to_ayah,
        )
        resp = HttpResponse(cached_resp, content_type="application/json")
        resp["Cache-Control"] = "public, max-age=300, s-maxage=300" if is_open_access else "private, no-cache"
        return resp

    # Cache miss - hit DB.
    repo = RecitationRepository()
    service = RecitationService(repo)

    asset = repo.get_asset_object(asset_id, Q(restricted_for_tenant=False))
    if not asset:
        raise Http404(str(_("No asset matches the given query.")))

    enforce_asset_access_on_public_api(getattr(request, "user", None), asset)

    # Publisher comes from the served Asset (select_related in get_asset_object).
    publisher_name = asset.publisher.name if asset.publisher_id else None
    asset_meta = {
        "name_ar": asset.name_ar,
        "publisher_id": asset.publisher_id,
        "publisher_name": publisher_name,
        "is_open_access": asset.is_open_access,
    }

    track_extra(
        request,
        entity_type="recitation_range",
        accessed_entity_name=asset.name_ar,
        entity_ids=[asset.id],
        entity_names=[asset.name_ar],
        publisher_ids=[asset.publisher_id] if asset.publisher_id else [],
        publisher_names=[publisher_name] if asset.publisher_id else [],
        surah_number=surah_number,
        from_ayah=from_ayah,
        to_ayah=to_ayah,
    )

    # Validate the range (422 on bad order/bounds/gaps) and resolve track+folder.
    track, resolved_folder, subset, start_ms, end_ms = service.get_range_segment(
        asset_id,
        surah_number,
        from_ayah,
        to_ayah,
        folder=folder,
        require_visible_folder=True,
    )

    # Serve the persisted clip when present; otherwise cut once from the surah
    # track (fades only at outer boundaries) and upload it under a
    # deterministic key so the next identical request is a cache/R2 hit.
    built = RecitationRangeService().get_or_build_range_audio(
        track, resolved_folder, surah_number, from_ayah, to_ayah, start_ms, end_ms, subset
    )

    payload = {
        "asset_id": asset.id,
        "surah_number": surah_number,
        "from_ayah": from_ayah,
        "to_ayah": to_ayah,
        "folder": resolved_folder.slug,
        "audio_url": built["audio_url"],
        "duration_ms": built["duration_ms"],
        "size_bytes": built["size_bytes"],
        "ayahs_timings": [
            {
                "ayah_key": t.ayah_key,
                "start_ms": t.start_ms,
                "end_ms": t.end_ms,
                "duration_ms": t.duration_ms,
                "offset_ms": t.start_ms - start_ms,
            }
            for t in subset
        ],
    }

    response_bytes = json.dumps(payload).encode()
    cache.set(_resp_key, response_bytes, RECITATION_RESPONSE_CACHE_TTL)
    cache.set(_meta_key, asset_meta, RECITATION_ASSET_META_CACHE_TTL)

    resp = HttpResponse(response_bytes, content_type="application/json")
    resp["Cache-Control"] = "public, max-age=300, s-maxage=300" if asset.is_open_access else "private, no-cache"
    return resp
