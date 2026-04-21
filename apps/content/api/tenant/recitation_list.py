from typing import Annotated

from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate

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


class RecitationQiraahOut(Schema):
    id: int
    name: str
    bio: str


class RecitationListOut(Schema):
    id: int
    name: str
    description: str
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviourChoice | None
    year: int | None
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut | None = None
    qiraah: RecitationQiraahOut


class RecitationFilter(FilterSchema):
    reciter_id: Annotated[list[int] | None, FilterLookup(q="reciter_id__in")] = None
    riwayah_id: Annotated[list[int] | None, FilterLookup(q="riwayah_id__in")] = None
    qiraah_id: Annotated[list[int] | None, FilterLookup(q="qiraah_id__in")] = None
    madd_level: Annotated[list[Asset.MaddLevelChoice] | None, FilterLookup(q="madd_level__in")] = None
    meem_behaviour: Annotated[list[Asset.MeemBehaviourChoice] | None, FilterLookup(q="meem_behaviour__in")] = None


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "publisher__name", "reciter__name"])
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("publisher")
    qs = service.get_all_recitations(publisher_q, filters)

    return qs
