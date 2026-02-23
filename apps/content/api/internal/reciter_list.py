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
    recitations_count: int = Field(
        0, description="Number of READY recitation assets for this reciter"
    )


class ReciterFilter(FilterSchema):
    publisher_id: list[int] | None = Field(
        None,
        q="assets__resource__publisher_id__in",
        description="Filter by publisher ID.",
    )


@router.get("reciters/", response=list[ReciterOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "name_ar", "slug"])
def list_reciters(request: Request, filters: ReciterFilter = Query()):
    """
    Internal CMS API: Search and list reciters with support for:
    - **Full-text search** by reciter name (Arabic & English) and slug.
    - **Filter by Publisher** (`publisher_id`): Limit reciters to those
      with READY recitations owned by the specified publisher(s).
    - **Server-side pagination** via `page` & `page_size` query parameters.
    - **Ordering** via `ordering` query parameter (name, -name, etc.).
    """
    repo = RecitationRepository()
    service = RecitationService(repo)
    publisher_q = request.publisher_q("assets__resource__publisher")
    qs = service.get_all_reciters(publisher_q, filters)
    return qs
