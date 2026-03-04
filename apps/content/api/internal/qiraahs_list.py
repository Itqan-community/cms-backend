"""
Qiraahs listing endpoint for CMS internal API.

GET /cms-api/qiraahs/  → List qiraahs for filter dropdowns (كل القراءات)
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


class RiwayahOut(Schema):
    id: int
    name: str
    slug: str


class QiraahListOut(Schema):
    """Qiraah item for dropdown / listing."""

    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    recitation_style: str | None = None
    riwayahs: list[RiwayahOut]
    recitations_count: int = Field(0, description="Number of READY recitation assets")


# ── Filters ─────────────────────────────────────────────────────────


class QiraahFilter(FilterSchema):
    name: str | None = Field(None, description="Filter by qiraah name (case-insensitive)")
    slug: str | None = Field(None, description="Filter by qiraah slug (case-insensitive)")
    is_active: bool | None = Field(None, description="Filter by active status")


# ── Endpoint ────────────────────────────────────────────────────────


@router.get("qiraahs/", response=list[QiraahListOut])
@paginate
@ordering(ordering_fields=["name"])
@searching(search_fields=["name", "slug"])
def list_qiraahs(request: Request, filters: QiraahFilter = Query()):
    """
    CMS Internal API: List qiraahs for the filter dropdown (كل القراءات).

    Only shows qiraahs that have at least one active riwayah
    with READY recitation assets.
    """
    repo = RecitationRepository()
    service = RiwayahService(repo)
    return service.get_all_qiraahs(
        publisher_q=request.publisher_q("riwayahs__assets__resource__publisher"),
        filters=filters,
    )
