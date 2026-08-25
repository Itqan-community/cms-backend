from typing import Literal

from ninja import Query, Schema

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.quran.models import Ayah, Sura
from apps.quran.repositories.quran import QuranRepository
from apps.quran.services.quran import QuranService

router = ItqanRouter(tags=[NinjaTag.SAMPLE_DATA])

DEFAULT_SAMPLE_SURAH = 1
DEFAULT_SAMPLE_AYAH = 1


class SuraSampleOut(Schema):
    """Public sample payload describing a single sura (Al-Fatiha by default)."""

    id: int
    name: str
    transliterated_name: str
    english_name: str
    ayas_count: int
    revelation_type: str
    revelation_order: int
    rukus_count: int


class AyahSampleOut(Schema):
    """Public sample payload for one ayah, exposing its Uthmani text and mushaf location."""

    id: int
    surah_id: int
    number_in_surah: int
    text_uthmani: str
    juz: int
    page: int
    hizb_quarter: int


def serialize_sura(sura: Sura) -> dict:
    """Map a ``Sura`` row onto the approved public contract field names."""
    # Keys are the approved public contract; the model column is sura_id but the
    # API exposes surah_id, so ORM objects are not returned directly.
    return {
        "id": sura.id,
        "name": sura.name,
        "transliterated_name": sura.transliterated_name,
        "english_name": sura.english_name,
        "ayas_count": sura.ayas_count,
        "revelation_type": sura.revelation_type,
        "revelation_order": sura.revelation_order,
        "rukus_count": sura.rukus_count,
    }


def serialize_ayah(ayah: Ayah) -> dict:
    """Map an ``Ayah`` row onto the approved public contract (Uthmani text included)."""
    return {
        "id": ayah.id,
        "surah_id": ayah.sura_id,
        "number_in_surah": ayah.number_in_sura,
        "text_uthmani": ayah.text_uthmani,
        "juz": ayah.juz,
        "page": ayah.page,
        "hizb_quarter": ayah.hizb_quarter,
    }


@router.get(
    "sample-data/surah/",
    response={
        200: SuraSampleOut,
        404: NinjaErrorResponse[Literal["sura_not_found"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_sura_sample(request: Request, surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114)):
    """Return a sample sura by number (default: Al-Fatiha, sura 1)."""
    service = QuranService(QuranRepository())
    return serialize_sura(service.get_sura(surah))


@router.get(
    "sample-data/ayah/",
    response={
        200: AyahSampleOut,
        404: NinjaErrorResponse[Literal["sura_not_found"]] | NinjaErrorResponse[Literal["ayah_not_found"]],
    },
    tags=[NinjaTag.SAMPLE_DATA],
)
def get_ayah_sample(
    request: Request,
    surah: int = Query(DEFAULT_SAMPLE_SURAH, ge=1, le=114),
    ayah: int = Query(DEFAULT_SAMPLE_AYAH, ge=1),
):
    """Return a sample ayah with its Uthmani text (default: 1:1)."""
    service = QuranService(QuranRepository())
    return serialize_ayah(service.get_ayah(surah, ayah))
