"""
Recitations listing endpoint.

GET /cms-api/recitations/
Supports: search by reciter name, filter by riwayah/qiraah/recitation_type,
pagination, ordering.

Maps to the recitation cards grid in the frontend UI.
"""

from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


# ── Response Schemas ────────────────────────────────────────────────


class RecitationReciterOut(Schema):
    id: int
    name: str
    name_en: str | None = None


class RecitationRiwayahOut(Schema):
    id: int
    name: str
    name_en: str | None = None


class RecitationQiraahOut(Schema):
    id: int
    name: str
    name_en: str | None = None


class RecitationListOut(Schema):
    """Recitation card data matching the frontend UI."""

    id: int
    name: str
    description: str
    recitation_type: Asset.RecitationTypeChoice | None
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviorChoice | None
    year: int | None
    format: str
    preview_audio_url: AbsoluteUrl | None = None
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut | None
    qiraah: RecitationQiraahOut | None


# ── Filters ─────────────────────────────────────────────────────────


class RecitationFilter(FilterSchema):
    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")
    qiraah_id: list[int] | None = Field(None, q="qiraah_id__in")
    recitation_type: list[str] | None = Field(None, q="recitation_type__in")


# ── Endpoint ────────────────────────────────────────────────────────


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    """
    List recitation assets with search, filter, pagination and ordering.

    Each result maps to a recitation card in the frontend showing:
    reciter name, qiraah, riwayah, recitation type (الأسلوب), madd level (الأداء).
    """
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("resource__publisher")
    qs = service.get_all_recitations(publisher_q, filters)

    return qs


@router.delete("recitations/{recitation_id}/", response={204: None})
def delete_recitation(request: Request, recitation_id: int):
    """
    CMS Internal API: Delete a recitation asset (trash icon on card).
    """
    publisher_q = request.publisher_q("resource__publisher")
    asset = Asset.objects.filter(publisher_q, id=recitation_id).get()
    asset.delete()
    return 204, None
