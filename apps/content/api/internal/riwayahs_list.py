"""
Riwayahs listing endpoint for CMS internal API.

GET /cms-api/riwayahs/  → List riwayahs for filter dropdowns (كل الروايات)
"""

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


# ── Response Schemas ────────────────────────────────────────────────


class QiraahOut(Schema):
    id: int
    name: str
    slug: str


class RiwayahListOut(Schema):
    """Riwayah item for dropdown / listing."""

    id: int
    name: str
    slug: str
    qiraah: QiraahOut
    recitations_count: int = Field(0, description="Number of READY recitation assets")


# ── Filters ─────────────────────────────────────────────────────────


class RiwayahFilter(FilterSchema):
    name: str | None = Field(None, description="Filter by riwayah name (case-insensitive)")
    slug: str | None = Field(None, description="Filter by riwayah slug (case-insensitive)")
    qiraah_id: int | None = Field(None, description="Filter by parent qiraah ID")


# ── Endpoint ────────────────────────────────────────────────────────


@router.get("riwayahs/", response=list[RiwayahListOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "slug"])
def list_riwayahs(request: Request, filters: RiwayahFilter = Query()):
    """
    CMS Internal API: List riwayahs for the filter dropdown (كل الروايات).

    Only shows riwayahs that have at least one READY recitation asset.
    """
    repo = RecitationRepository()
    service = RiwayahService(repo)
    return service.get_all_riwayahs(
        publisher_q=request.publisher_q("assets__resource__publisher"),
        filters=filters,
    )
