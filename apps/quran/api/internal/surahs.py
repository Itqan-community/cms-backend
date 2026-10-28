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


class SurahOut(Schema):
    id: int
    name: str
    transliterated_name: str
    english_name: str
    ayahs_count: int
    start_offset: int
    revelation_type: str
    revelation_order: int
    rukus_count: int


@router.get("surahs/", response=list[SurahOut])
@paginate
def list_surahs(request: Request):
    """List all 114 surahs, ordered by surah number."""
    service = QuranService(QuranRepository())
    return service.list_surahs()


@router.get(
    "surahs/{int:surah_id}/",
    response={200: SurahOut, 404: NinjaErrorResponse[Literal["surah_not_found"]]},
)
def get_surah(request: Request, surah_id: int):
    """Retrieve a single surah by its number."""
    service = QuranService(QuranRepository())
    return service.get_surah(surah_id)
