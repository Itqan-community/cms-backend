"""
Reciters listing and creation endpoints for CMS internal API.

GET  /cms-api/reciters/          → List reciters (search, filter, paginate)
POST /cms-api/reciters/create/   → Create a new reciter (إضافة قارئ)
"""

from ninja import FilterSchema, Query, Schema
from ninja.files import UploadedFile
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Reciter
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITERS])


# ── Response Schemas ────────────────────────────────────────────────


class ReciterListOut(Schema):
    """Reciter card in the CMS dashboard."""

    id: int
    name: str
    slug: str
    bio: str
    image_url: AbsoluteUrl | None
    is_active: bool
    recitations_count: int = Field(0, description="Number of READY recitation assets")


class ReciterCreateOut(Schema):
    """Response after creating a reciter."""

    id: int
    name: str
    slug: str


# ── Filters ─────────────────────────────────────────────────────────


class ReciterFilter(FilterSchema):
    name: list[str] | None = Field(None, q="name__in")
    name_ar: list[str] | None = Field(None, q="name_ar__in")
    slug: list[str] | None = Field(None, q="slug__in")


# ── Create Schema ───────────────────────────────────────────────────


class ReciterCreateIn(Schema):
    """Payload for creating a new reciter."""

    name: str
    name_ar: str | None = None
    bio: str = ""


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("reciters/", response=list[ReciterListOut])
@paginate
@ordering(ordering_fields=["name", "created_at"])
@searching(search_fields=["name", "name_ar", "slug"])
def list_reciters(request: Request, filters: ReciterFilter = Query()):
    """
    CMS Internal API: List reciters with recitation count.

    Supports:
    - Search (ابحث عن قارئ)
    - Pagination
    - Ordering
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("assets__resource__publisher")
    qs = service.get_all_reciters(publisher_q, filters)

    return qs


@router.post("reciters/create/", response={201: ReciterCreateOut})
def create_reciter(request: Request, payload: ReciterCreateIn):
    """
    CMS Internal API: Create a new reciter (إضافة قارئ).
    """
    reciter = Reciter(
        name=payload.name,
        bio=payload.bio,
    )
    if payload.name_ar:
        reciter.name_ar = payload.name_ar
    reciter.save()

    return 201, reciter
