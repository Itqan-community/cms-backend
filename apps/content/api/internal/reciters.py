from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag


router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterOut(Schema):
    id: int
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this reciter",
    )


class ReciterFilter(FilterSchema):
    name: list[str] | None = Field(None, q="name__in")
    name_ar: list[str] | None = Field(None, q="name_ar__in")
    slug: list[str] | None = Field(None, q="slug__in")


@router.get("reciters/", response=list[ReciterOut], auth=None)
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "name_en", "name_ar", "slug"])
def list_reciters(request: Request, filters: ReciterFilter = Query()):
    """
    CMS Internal API:

    List reciters that have at least one READY recitation Asset
    for the current publisher (tenant), with full-text search
    over Arabic and English names.
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("assets__resource__publisher")
    qs = service.get_all_reciters(publisher_q, filters)

    return qs

