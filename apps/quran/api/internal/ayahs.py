from typing import Literal

from ninja import Schema

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.quran.repositories.quran import QuranRepository
from apps.quran.services.quran import QuranService

router = ItqanRouter(tags=[NinjaTag.QURAN])


class WordOut(Schema):
    id: int
    position_in_ayah: int
    text: str


class AyahOut(Schema):
    id: int
    surah_id: int
    number_in_surah: int
    text: str
    juz: int
    hizb_quarter: int
    page: int
    words: list[WordOut]


@router.get(
    "surahs/{int:surah_id}/ayahs/",
    response={200: list[AyahOut], 404: NinjaErrorResponse[Literal["surah_not_found"]]},
)
def list_ayahs(request: Request, surah_id: int):
    """List all ayahs of a surah (with their words), ordered within the surah."""
    service = QuranService(QuranRepository())
    return service.list_ayahs_for_surah(surah_id)


@router.get(
    "surahs/{int:surah_id}/ayahs/{int:number_in_surah}/",
    response={
        200: AyahOut,
        404: NinjaErrorResponse[Literal["surah_not_found"]] | NinjaErrorResponse[Literal["ayah_not_found"]],
    },
)
def get_ayah(request: Request, surah_id: int, number_in_surah: int):
    """Retrieve a single ayah (with its words) by surah number and ayah number."""
    service = QuranService(QuranRepository())
    return service.get_ayah(surah_id, number_in_surah)
