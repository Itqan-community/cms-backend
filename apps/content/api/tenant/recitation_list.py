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

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationReciterOut(Schema):
    id: int
    name: str


class RecitationRiwayahOut(Schema):
    id: int
    name: str


class RecitationListOut(Schema):
    id: int
    name: str
    description: str
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviorChoice | None
    year: int | None
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut


class RecitationFilter(FilterSchema):
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")
    qiraah_id: list[int] | None = Field(None, q="qiraah_id__in")
    madd_level: list[Asset.MaddLevelChoice] | None = Field(None, q="madd_level__in")
    meem_behaviour: list[Asset.MeemBehaviorChoice] | None = Field(None, q="meem_behaviour__in")


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("resource__publisher")
    qs = service.get_all_recitations(publisher_q, filters)

    return qs
