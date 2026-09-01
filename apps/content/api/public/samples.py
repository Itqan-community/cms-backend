from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Query, Schema

from apps.content.models import Asset, RecitationSurahTrack
from apps.content.repositories.recitation import RecitationRepository
from apps.content.repositories.tafsir import TafsirRepository
from apps.content.repositories.translation import TranslationRepository
from apps.content.services.asset_verse_text import extract_verse_text
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.quran.api.public.samples import (
    DEFAULT_SAMPLE_AYAH,
    DEFAULT_SAMPLE_SURAH,
    AyahSampleOut,
    SuraSampleOut,
    serialize_ayah,
    serialize_sura,
)
from apps.quran.repositories.quran import QuranRepository
from apps.quran.services.quran import QuranService
from config.settings.base import CLOUDFLARE_R2_PUBLIC_BASE_URL

router = ItqanRouter(tags=[NinjaTag.SAMPLE_DATA])


class PublisherMinimalOut(Schema):
    """Minimal publisher identity embedded inside sample payloads."""

    id: int
    name: str


class ReciterOut(Schema):
    """Reciter identity rendered by the recitation sample."""

    id: int
    name: str


class RiwayahOut(Schema):
    """Narration/qiraah identity rendered by the recitation sample."""

    id: int
    name: str


class AyahTimingOut(Schema):
    """Single ayah timing window in playback order."""

    ayah_number: int
    start_ms: int
    end_ms: int


class SampleTrackOut(Schema):
    """One surah audio track with its playback metadata and full timing map."""

    surah_number: int
    audio_url: str
    duration_ms: int
    ayah_timings: list[AyahTimingOut]


class RecitationSampleOut(Schema):
    """Media-player-ready recitation sample: identities plus the default surah track."""

    id: int
    name: str
    reciter: ReciterOut
    riwayah: RiwayahOut
    qiraah: RiwayahOut
    publisher: PublisherMinimalOut
    sample_track: SampleTrackOut


class SampleVerseOut(Schema):
    """The anchored verse a content asset actually provides text for."""

    surah: int
    ayah: int
    text: str


class TafsirSampleOut(Schema):
    """Tafsir sample payload; ``sample_verse.text`` is read from the version file."""

    asset_id: int
    asset_name: str
    publisher: PublisherMinimalOut
    language: str
    license: str
    sample_verse: SampleVerseOut


class TranslationSampleOut(Schema):
    """Translation sample payload; ``sample_verse.text`` is read from the version file."""

    asset_id: int
    asset_name: str
    publisher: PublisherMinimalOut
    language: str
    license: str
    sample_verse: SampleVerseOut


def _content_section(asset: Asset, surah: int, ayah: int) -> dict | None:
    """
    Tafsir/translation payload for one ayah, read from the asset's latest
    version file. Returns None when the file cannot provide the verse -- joined
    responses degrade to a null section instead of fabricating text.
    """
    text = extract_verse_text(asset, surah, ayah)
    if text is None:
        return None
    return {
        "asset_id": asset.id,
        "asset_name": asset.name,
        "publisher": {"id": asset.publisher_id, "name": asset.publisher.name},
        "language": asset.language,
        "license": asset.license,
        "sample_verse": {"surah": surah, "ayah": ayah, "text": text},
    }


@router.get(
    "sample-data/tafsir/",
    response={
        200: TafsirSampleOut,
        404: NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_sample_verse_unavailable"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_tafsir_sample(
    request: Request,
    surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114),
    ayah: int = Query(DEFAULT_SAMPLE_AYAH, ge=1),
):
    """Sample tafsir verse, read from the asset's latest version file (never fabricated)."""
    asset = TafsirRepository().get_ready_asset()
    if asset is None:
        raise ItqanError(
            error_name="tafsir_not_found",
            message=_("No tafsir available"),
            status_code=404,
        )

    section = _content_section(asset, surah, ayah)
    if section is None:
        raise ItqanError(
            error_name="tafsir_sample_verse_unavailable",
            message=_("This tafsir does not provide text for surah {surah}, ayah {ayah}.").format(
                surah=surah, ayah=ayah
            ),
            status_code=404,
        )
    return section


@router.get(
    "sample-data/translation/",
    response={
        200: TranslationSampleOut,
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["translation_sample_verse_unavailable"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_translation_sample(
    request: Request,
    surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114),
    ayah: int = Query(DEFAULT_SAMPLE_AYAH, ge=1),
):
    """Sample translation verse, read from the asset's latest version file (never fabricated)."""
    asset = TranslationRepository().get_ready_asset()
    if asset is None:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("No translation available"),
            status_code=404,
        )

    section = _content_section(asset, surah, ayah)
    if section is None:
        raise ItqanError(
            error_name="translation_sample_verse_unavailable",
            message=_("This translation does not provide text for surah {surah}, ayah {ayah}.").format(
                surah=surah, ayah=ayah
            ),
            status_code=404,
        )
    return section


@router.get(
    "sample-data/recitation/",
    response={
        200: RecitationSampleOut,
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_recitation_sample(request: Request, surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114)):
    """Media-player sample: a complete recitation with its default surah track and full ayah timings."""
    service = RecitationService(RecitationRepository())
    asset = service.get_sample_recitation()
    if asset is None:
        raise ItqanError(
            error_name="recitation_not_found",
            message=_("No recitation available"),
            status_code=404,
        )

    track = service.get_sample_track(asset.id, surah)
    if track is None:
        raise ItqanError(
            error_name="recitation_not_found",
            message=_("No recitation track available for surah {surah}.").format(surah=surah),
            status_code=404,
        )
    return _recitation_payload(asset, track)


def _recitation_payload(asset: Asset, track: RecitationSurahTrack) -> dict:
    """
    Build the media-player payload for one recitation asset and its track.

    Timings are parsed from ``"<surah>:<ayah>"`` keys into ordered
    ``ayah_number`` entries; malformed keys are skipped rather than guessed.
    """
    # get_sample_asset() only returns complete assets; the guard keeps the
    # invariant explicit and satisfies null-safety for the FK accesses below.
    reciter, riwayah, qiraah = asset.reciter, asset.riwayah, asset.qiraah
    if reciter is None or riwayah is None or qiraah is None:
        raise ItqanError(
            error_name="recitation_not_found",
            message=_("No recitation available"),
            status_code=404,
        )

    parsed_timings = []
    for timing in track.ayah_timings.all():
        ayah_number = _ayah_number_from_key(timing.ayah_key)
        if ayah_number is not None:
            parsed_timings.append({"ayah_number": ayah_number, "start_ms": timing.start_ms, "end_ms": timing.end_ms})

    return {
        "id": asset.id,
        "name": asset.name,
        "reciter": {"id": reciter.id, "name": reciter.name},
        "riwayah": {"id": riwayah.id, "name": riwayah.name},
        "qiraah": {"id": qiraah.id, "name": qiraah.name},
        "publisher": {"id": asset.publisher_id, "name": asset.publisher.name},
        "sample_track": {
            "surah_number": track.surah_number,
            "audio_url": f"{CLOUDFLARE_R2_PUBLIC_BASE_URL}/media/{track.audio_file.name}",
            "duration_ms": track.duration_ms,
            "ayah_timings": parsed_timings,
        },
    }


def _ayah_number_from_key(ayah_key: str) -> int | None:
    """Parse the trailing ayah number from a ``"<surah>:<ayah>"`` timing key."""
    try:
        return int(str(ayah_key).rsplit(":", 1)[-1])
    except ValueError:
        return None


class JoinedAyahSampleOut(Schema):
    """One ayah joined across domains; content sections degrade to null, never fabricate."""

    surah: SuraSampleOut
    ayah: AyahSampleOut
    tafsir: TafsirSampleOut | None = None
    translation: TranslationSampleOut | None = None
    recitation: RecitationSampleOut | None = None


@router.get(
    "sample-data/joined-ayah/",
    response={
        200: JoinedAyahSampleOut,
        404: NinjaErrorResponse[Literal["sura_not_found"]] | NinjaErrorResponse[Literal["ayah_not_found"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_joined_ayah(
    request: Request,
    surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114),
    ayah: int = Query(DEFAULT_SAMPLE_AYAH, ge=1),
):
    """Developer sample joining one ayah's Quran reference data, content texts, and recitation.

    The requested location anchors the response; content sections whose assets
    cannot provide that exact verse degrade to null rather than fabricating text.
    """
    # get_ayah selects the sura in the same query (repository pattern) -- the
    # surah section costs no extra round-trip and 404s use the canonical names.
    ayah_obj = QuranService(QuranRepository()).get_ayah(surah, ayah)
    sura = ayah_obj.sura

    tafsir_asset = TafsirRepository().get_ready_asset()
    translation_asset = TranslationRepository().get_ready_asset()

    recitation_service = RecitationService(RecitationRepository())
    recitation_asset = recitation_service.get_sample_recitation()
    track = recitation_service.get_sample_track(recitation_asset.id, surah) if recitation_asset else None

    return {
        "surah": serialize_sura(sura),
        "ayah": serialize_ayah(ayah_obj),
        "tafsir": _content_section(tafsir_asset, surah, ayah) if tafsir_asset else None,
        "translation": _content_section(translation_asset, surah, ayah) if translation_asset else None,
        "recitation": _recitation_payload(recitation_asset, track) if recitation_asset and track else None,
    }
