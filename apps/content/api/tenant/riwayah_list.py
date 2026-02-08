from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.riwayah import RiwayahService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RIWAYAHS])


class RiwayahOut(Schema):
    id: int
    name: str
    slug: str
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this riwayah",
    )


class RiwayahFilter(FilterSchema):
    name: str | None = Field(None, description="Filter by riwayah name (case-insensitive)")
    slug: str | None = Field(None, description="Filter by riwayah slug (case-insensitive)")


@router.get("riwayahs/", response=list[RiwayahOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "slug"])
def list_riwayahs(request: Request, filters: RiwayahFilter = Query()):
    """
    Public Content API (V2):

    List riwayahs that have at least one READY recitation Asset.

    Conditions:
    - Riwayah.is_active = True
    - Asset.category = RECITATION
    - Asset.riwayah = this Riwayah
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    """
    repo = RecitationRepository()
    service = RiwayahService(repo)
    return service.get_all_riwayahs(publisher_q=request.publisher_q("assets__resource__publisher"), filters=filters)
