from typing import Literal

from ninja import Schema

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.quran.repositories.quran import QuranRepository
from apps.quran.services.quran import QuranService

router = ItqanRouter(tags=[NinjaTag.QURAN])


class HierarchySuraOut(Schema):
    id: int
    name: str
    transliterated_name: str
    english_name: str
    ayas_count: int
    start_offset: int


class HierarchyAyahOut(Schema):
    id: int
    number_in_sura: int
    text: str
    words_count: int


class HierarchyWordOut(Schema):
    id: int
    position_in_ayah: int
    text: str


@router.get("hierarchy/tree/", response=list[HierarchySuraOut])
def list_hierarchy_tree(request: Request):
    """List all 114 suras with summary fields for hierarchy root expansion."""
    service = QuranService(QuranRepository())
    return service.list_hierarchy_tree()


@router.get(
    "hierarchy/surah/{int:sura_id}/tree/",
    response={200: list[HierarchyAyahOut], 404: NinjaErrorResponse[Literal["sura_not_found"]]},
)
def list_surah_ayah_tree(request: Request, sura_id: int):
    """List ayahs of a sura with word counts (no word rows) for lazy tree expand."""
    service = QuranService(QuranRepository())
    return service.list_surah_ayah_tree(sura_id)


@router.get(
    "hierarchy/ayah/{int:sura_id}/{int:number_in_sura}/words/",
    response={
        200: list[HierarchyWordOut],
        404: NinjaErrorResponse[Literal["ayah_not_found"]],
    },
)
def get_ayah_words(request: Request, sura_id: int, number_in_sura: int):
    """Return ordered words for a single ayah (drill-down leaf)."""
    service = QuranService(QuranRepository())
    return service.get_ayah_words(sura_id, number_in_sura)
