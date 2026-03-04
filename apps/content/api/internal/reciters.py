from typing import Annotated, Literal

from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag


router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterOut(Schema):
    id: int
    name: str
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this reciter",
    )


class ReciterFilter(FilterSchema):
    name: Annotated[list[str] | None, FilterLookup("name__in")] = None
    name_ar: Annotated[list[str] | None, FilterLookup("name_ar__in")] = None
    slug: Annotated[list[str] | None, FilterLookup("slug__in")] = None


@router.get(
    "reciters/",
    response={
        200: list[ReciterOut],
        400: NinjaErrorResponse[Literal["validation_error"], Literal[None]],
        403: NinjaErrorResponse[Literal["permission_denied"], Literal[None]],
    },
)
@paginate
@ordering(ordering_fields=["name", "name_ar"])
@searching(search_fields=["name", "name_ar", "slug"])
def list_reciters(request: Request, filters: Query[ReciterFilter]):
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

