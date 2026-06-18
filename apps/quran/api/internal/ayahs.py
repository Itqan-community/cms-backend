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
    sura_id: int
    number_in_sura: int
    text: str
    juz: int
    hizb_quarter: int
    page: int
    words: list[WordOut]


@router.get(
    "suras/{int:sura_id}/ayahs/",
    response={200: list[AyahOut], 404: NinjaErrorResponse[Literal["sura_not_found"]]},
)
def list_ayahs(request: Request, sura_id: int):
    """List all ayahs of a sura (with their words), ordered within the sura."""
    service = QuranService(QuranRepository())
    return service.list_ayahs_for_sura(sura_id)


@router.get(
    "suras/{int:sura_id}/ayahs/{int:number_in_sura}/",
    response={
        200: AyahOut,
        404: NinjaErrorResponse[Literal["sura_not_found"]] | NinjaErrorResponse[Literal["ayah_not_found"]],
    },
)
def get_ayah(request: Request, sura_id: int, number_in_sura: int):
    """Retrieve a single ayah (with its words) by sura number and ayah number."""
    service = QuranService(QuranRepository())
    return service.get_ayah(sura_id, number_in_sura)
