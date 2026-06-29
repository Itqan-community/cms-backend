from typing import Literal

from ninja import Schema
from ninja.pagination import paginate

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.quran.repositories.quran import QuranRepository
from apps.quran.services.quran import QuranService

router = ItqanRouter(tags=[NinjaTag.QURAN])


class SuraOut(Schema):
    id: int
    name: str
    transliterated_name: str
    english_name: str
    ayas_count: int
    start_offset: int
    revelation_type: str
    revelation_order: int
    rukus_count: int


@router.get("suras/", response=list[SuraOut])
@paginate
def list_suras(request: Request):
    """List all 114 suras, ordered by sura number."""
    service = QuranService(QuranRepository())
    return service.list_suras()


@router.get(
    "suras/{int:sura_id}/",
    response={200: SuraOut, 404: NinjaErrorResponse[Literal["sura_not_found"]]},
)
def get_sura(request: Request, sura_id: int):
    """Retrieve a single sura by its number."""
    service = QuranService(QuranRepository())
    return service.get_sura(sura_id)
