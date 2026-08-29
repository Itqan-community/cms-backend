import json
from typing import Literal

from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse
from ninja import Query, Schema

from apps.content.cache import (
    RECITATION_ASSET_META_CACHE_TTL,
    RECITATION_AYAH_RESPONSE_CACHE_TTL,
    folder_cache_token,
    recitation_asset_meta_cache_key,
    recitation_ayah_response_cache_key,
)
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.asset_access import enforce_asset_access_on_public_api
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationAyahAudioOut(Schema):
    """Output schema representing an individual Ayah audio track and its playback metadata."""

    ayah_key: str
    surah_number: int
    ayah_number: int
    duration_ms: int
    size_bytes: int | None = None
    audio_url: str


@router.get(
    "recitations/{asset_id}/ayah/{ayah_key}/",
    response={
        200: RecitationAyahAudioOut,
        401: NinjaErrorResponse[Literal["authentication_required"]],
        403: NinjaErrorResponse[Literal["access_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]]
        | NinjaErrorResponse[Literal["folder_not_found"]]
        | NinjaErrorResponse[Literal["ayah_not_found"]],
    },
)
@track_usage(entity_type="recitation")
def get_recitation_ayah(
    request: Request,
    asset_id: int,
    ayah_key: str,
    folder: str | None = Query(None),
):
    """
    Public developers API endpoint to return audio URL and metadata for a single Ayah.
    """
    token = folder_cache_token(folder)
    _resp_key = recitation_ayah_response_cache_key(asset_id, token, ayah_key)
    _meta_key = recitation_asset_meta_cache_key(asset_id)

    cached_resp: bytes | None = cache.get(_resp_key)
    cached_meta: dict | None = cache.get(_meta_key)

    if cached_resp is not None and cached_meta is not None and "is_open_access" in cached_meta:
        is_open_access: bool = cached_meta["is_open_access"]
        if not is_open_access:
            enforce_asset_access_on_public_api(
                getattr(request, "user", None),
                asset_id=asset_id,
                is_open_access=is_open_access,
            )

        track_extra(
            request,
            entity_type="recitation",
            accessed_entity_name=cached_meta["name_ar"],
            entity_ids=[asset_id],
            entity_names=[cached_meta["name_ar"]],
            publisher_ids=[cached_meta["publisher_id"]] if cached_meta["publisher_id"] else [],
            publisher_names=[cached_meta["publisher_name"]] if cached_meta["publisher_id"] else [],
            folder=folder,
            ayah_key=ayah_key,
        )
        resp = HttpResponse(cached_resp, content_type="application/json")
        resp["Cache-Control"] = "public, max-age=300, s-maxage=300" if is_open_access else "private, no-cache"
        return resp

    # Cache miss - query service & repository
    repo = RecitationRepository()
    service = RecitationService(repo)

    data = service.get_ayah_audio_data(
        asset_id=asset_id,
        ayah_key=ayah_key,
        folder=folder,
        publisher_q=Q(restricted_for_tenant=False),
        require_visible_folder=True,
    )

    asset = data["asset"]
    enforce_asset_access_on_public_api(getattr(request, "user", None), asset)

    publisher_name = asset.publisher.name if asset.publisher_id else None
    asset_meta = {
        "name_ar": asset.name_ar,
        "publisher_id": asset.publisher_id,
        "publisher_name": publisher_name,
        "is_open_access": asset.is_open_access,
    }

    track_extra(
        request,
        entity_type="recitation",
        accessed_entity_name=asset.name_ar,
        entity_ids=[asset.id],
        entity_names=[asset.name_ar],
        publisher_ids=[asset.publisher_id] if asset.publisher_id else [],
        publisher_names=[publisher_name] if asset.publisher_id else [],
        folder=folder,
        ayah_key=data["ayah_key"],
    )

    result_payload = {
        "ayah_key": data["ayah_key"],
        "surah_number": data["surah_number"],
        "ayah_number": data["ayah_number"],
        "duration_ms": data["duration_ms"],
        "size_bytes": data["size_bytes"],
        "audio_url": data["audio_url"],
    }

    serialized_out = RecitationAyahAudioOut(**result_payload).model_dump()
    response_bytes = json.dumps(serialized_out).encode("utf-8")

    cache.set(_resp_key, response_bytes, RECITATION_AYAH_RESPONSE_CACHE_TTL)
    cache.set(_meta_key, asset_meta, RECITATION_ASSET_META_CACHE_TTL)

    resp = HttpResponse(response_bytes, content_type="application/json")
    resp["Cache-Control"] = "public, max-age=300, s-maxage=300" if asset.is_open_access else "private, no-cache"
    return resp
