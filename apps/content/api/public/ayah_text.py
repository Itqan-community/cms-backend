import json
from typing import Literal

from django.core.cache import cache
from django.http import HttpResponse
from ninja import Query, Schema
from pydantic import Field

from apps.content.cache import AYAH_TEXT_RESPONSE_CACHE_TTL, ayah_text_response_cache_key
from apps.content.services.asset_access import PublicAssetRef, enforce_assets_access_on_public_api
from apps.content.services.ayah_text import (
    MAX_ASSETS_PER_REQUEST,
    MAX_AYAHS_PER_REQUEST,
    AyahTextService,
    parse_asset_slugs,
    parse_ayah_key,
)
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_usage import track_extra, track_usage

router = ItqanRouter(tags=[NinjaTag.TEXT_ASSETS])


class AyahTextPositionOut(Schema):
    ayah_key: str = Field(..., description="'surah:ayah', e.g. '2:255'.")
    word_position: int | None = Field(None, description="Word position in the ayah (word-based assets only).")


class AyahTextRowOut(Schema):
    start: AyahTextPositionOut = Field(..., description="Where the row's unit starts.")
    end: AyahTextPositionOut = Field(
        ..., description="Where it ends: the same as start except for ayah / word groups, which may span ayahs."
    )
    cells: dict[str, str] = Field(..., description="One text per column key ('' when the cell is empty).")


class AyahTextColumnOut(Schema):
    key: str
    label_en: str
    label_ar: str


class AyahTextAssetOut(Schema):
    slug: str
    name_en: str
    name_ar: str
    category: Literal["text"]
    tags: list[str] = Field(..., description="What kind of text this is, e.g. ['tafsir'] or ['translation'].")
    template: Literal["ayah", "ayah_group", "word", "word_group"]
    language: str = Field(..., description="Language of the served (source) rendition.")
    version: str = Field(..., description="The published version served.")
    columns: list[AyahTextColumnOut]
    rows: list[AyahTextRowOut] = Field(
        ..., description="The asset's units covering the requested ayahs, in Quran order; empty when it has none."
    )


class AyahTextOut(Schema):
    surah_number: int
    from_ayah: int
    to_ayah: int
    assets: list[AyahTextAssetOut] = Field(..., description="One item per requested asset, in request order.")


class AssetSlugsExtra(Schema):
    assets: list[str] = Field(..., description="The requested slugs that caused the error.")


def _cache_control(refs: list[PublicAssetRef]) -> str:
    # Shared caches may keep the response only when every asset in it is open.
    if all(ref.is_open_access for ref in refs):
        return "public, max-age=300, s-maxage=300"
    return "private, no-cache"


def _track(request: Request, meta: list[dict], ayah_key: str, to_ayah: int | None) -> None:
    publishers = {item["publisher_id"]: item["publisher_name"] for item in meta if item["publisher_id"]}
    track_extra(
        request,
        entity_type="text",
        accessed_entity_name=", ".join(item["name_ar"] for item in meta),
        entity_ids=[item["id"] for item in meta],
        entity_names=[item["name_ar"] for item in meta],
        publisher_ids=list(publishers),
        publisher_names=list(publishers.values()),
        ayah_key=ayah_key,
        to_ayah=to_ayah,
    )


@router.get(
    "ayahs/{ayah_key}/",
    response={
        200: AyahTextOut,
        400: NinjaErrorResponse[Literal["assets_required"]]
        | NinjaErrorResponse[Literal["too_many_assets"]]
        | NinjaErrorResponse[Literal["invalid_ayah_range"]]
        | NinjaErrorResponse[Literal["asset_not_text"], AssetSlugsExtra]
        | NinjaErrorResponse[Literal["asset_not_ayah_based"], AssetSlugsExtra],
        401: NinjaErrorResponse[Literal["authentication_required"], AssetSlugsExtra],
        403: NinjaErrorResponse[Literal["access_denied"], AssetSlugsExtra],
        404: NinjaErrorResponse[Literal["ayah_not_found"]]
        | NinjaErrorResponse[Literal["asset_not_found"], AssetSlugsExtra],
    },
)
@track_usage(entity_type="text")
def get_ayah_text(
    request: Request,
    ayah_key: str,
    assets: list[str] | None = Query(
        None,
        description=(
            f"Slugs of the text assets to return (tafsirs, translations, ...), comma-separated and/or repeated; "
            f"at most {MAX_ASSETS_PER_REQUEST}. Only these assets are returned, in this order."
        ),
    ),
    to_ayah: int | None = Query(
        None,
        alias="to",
        ge=1,
        description=(
            f"Last ayah number of a range in the same surah (inclusive); at most {MAX_AYAHS_PER_REQUEST} ayahs. "
            "Omit for one ayah."
        ),
    ),
):
    """
    The content of several text assets (tafsirs, translations, ...) for one ayah, or a short
    range of ayahs in one surah, in one call.

    Each asset is served at its published version in its source language, with its columns
    (keys and labels) and the rows covering the ayahs: the ayah itself, its words, or the ayah /
    word groups that overlap it. Surah- and page-based assets can't be read per ayah.

    Open assets need no API key. Restricted ones need an API key whose owner holds an approved
    access request for each of them, like the recitation endpoints.
    """
    surah, from_ayah = parse_ayah_key(ayah_key)
    slugs = parse_asset_slugs(assets)
    cache_key = ayah_text_response_cache_key(surah, from_ayah, to_ayah or from_ayah, slugs)

    cached: dict | None = cache.get(cache_key)
    if cached is not None:
        # Warm path: access is still checked live (no query when every asset is open).
        refs = [PublicAssetRef(**ref) for ref in cached["refs"]]
        enforce_assets_access_on_public_api(getattr(request, "user", None), refs)
        _track(request, cached["meta"], ayah_key, to_ayah)
        resp = HttpResponse(cached["body"], content_type="application/json; charset=utf-8")
        resp["Cache-Control"] = _cache_control(refs)
        return resp

    service = AyahTextService()
    window = service.resolve_window(ayah_key, surah, from_ayah, to_ayah)
    served = service.resolve_assets(slugs)
    refs = [item.ref for item in served]
    enforce_assets_access_on_public_api(getattr(request, "user", None), refs)

    meta = [
        {
            "id": item.asset.pk,
            "name_ar": item.asset.name_ar or "",
            "publisher_id": item.asset.publisher_id,
            "publisher_name": item.asset.publisher.name if item.asset.publisher_id else None,
        }
        for item in served
    ]
    _track(request, meta, ayah_key, to_ayah)

    payload = AyahTextOut(**service.build_payload(window, served)).model_dump()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cache.set(
        cache_key,
        {"body": body, "refs": [ref.__dict__ for ref in refs], "meta": meta},
        AYAH_TEXT_RESPONSE_CACHE_TTL,
    )

    resp = HttpResponse(body, content_type="application/json; charset=utf-8")
    resp["Cache-Control"] = _cache_control(refs)
    return resp
