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


class QiraahOut(Schema):
    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    riwayahs: list[RiwayahOut]
    recitations_count: int = Field(0, description="Number of READY recitation assets for this qiraah")


class QiraahFilter(FilterSchema):
    name: str | None = Field(None, description="Filter by qiraah name (case-insensitive)")
    slug: str | None = Field(None, description="Filter by qiraah slug (case-insensitive)")
    is_active: bool | None = Field(None, description="Filter by active status")


@router.get("qiraahs/", response=list[QiraahOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "slug"])
def list_qiraahs(request: Request, filters: QiraahFilter = Query()):
    """
    List qiraahs (recitation methods) that have at least one active riwayah
    with READY recitation assets.

    Conditions:
    - Qiraah.is_active = True
    - Qiraah.riwayah.is_active = True
    - Asset.category = RECITATION
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    """
    repo = RecitationRepository()
    service = RiwayahService(repo)
    return service.get_all_qiraahs(
        publisher_q=request.publisher_q("riwayahs__assets__resource__publisher"), filters=filters
    )
