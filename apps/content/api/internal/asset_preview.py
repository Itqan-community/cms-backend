"""Gallery: a sample of what a recitation sounds like or a font looks like."""

from typing import Literal

from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.content.models import Asset
from apps.content.services.asset_preview import AssetPreviewService
from apps.core.mixins.constants import QURAN_SURAHS
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class PreviewTrackOut(Schema):
    surah_number: int
    surah_name: str
    surah_name_en: str
    audio_url: AbsoluteUrl
    duration_ms: int


class RecitationPreviewOut(Schema):
    tracks: list[PreviewTrackOut]


class SampleAyahOut(Schema):
    ayah: int
    text: str


class FontPreviewOut(Schema):
    font_url: AbsoluteUrl
    file_name: str
    format: Literal["woff2", "woff", "truetype", "opentype"]
    sample: list[SampleAyahOut]


def _gallery_asset(request: Request, id: int) -> Asset:
    return get_object_or_404(Asset, request.publisher_q("publisher"), restricted_for_tenant=False, id=id)


@router.get(
    "assets/{id}/recitation-preview/",
    response={200: RecitationPreviewOut, 404: NinjaErrorResponse[Literal["recitation_preview_unavailable"]]},
    auth=None,
)
def asset_recitation_preview(request: Request, id: int):
    """The first few surahs of a recitation's default folder, to play in the gallery."""
    tracks = AssetPreviewService().recitation_tracks(_gallery_asset(request, id), request)
    return {
        "tracks": [
            {
                "surah_number": track.surah_number,
                "surah_name": QURAN_SURAHS[track.surah_number]["name"],
                "surah_name_en": QURAN_SURAHS[track.surah_number]["name_en"],
                "audio_url": url,
                "duration_ms": track.duration_ms,
            }
            for track, url in tracks
        ]
    }


@router.get(
    "assets/{id}/font-preview/",
    response={200: FontPreviewOut, 404: NinjaErrorResponse[Literal["font_preview_unavailable"]]},
    auth=None,
)
def asset_font_preview(request: Request, id: int, language: str | None = None):
    """A font's file (the font inside a zip upload) and Al-Fatiha to render in it,
    for one language (default: the source)."""
    preview = AssetPreviewService().font(_gallery_asset(request, id), language, request)
    return {
        "font_url": preview.url,
        "file_name": preview.file_name,
        "format": preview.format,
        "sample": [{"ayah": ayah.number_in_sura, "text": ayah.text} for ayah in preview.sample],
    }
