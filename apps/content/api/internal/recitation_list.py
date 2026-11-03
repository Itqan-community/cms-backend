from typing import Annotated

from django.db.models import Q
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate

from apps.content.models import Asset
from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.content.services.recitation_quality_resolution import sorted_asset_qualities
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_search import track_search
from apps.usage_tracking.models import SearchSurface

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationQiraahOut(Schema):
    id: int
    name: str
    bio: str


class RecitationReciterOut(Schema):
    id: int
    name: str


class RecitationRiwayahOut(Schema):
    id: int
    name: str


class RecitationQualityOut(Schema):
    name: str
    slug: str
    is_default: bool


class RecitationListOut(Schema):
    id: int
    name: str
    description: str
    madd_level: Asset.MaddLevelChoice | None
    meem_behaviour: Asset.MeemBehaviourChoice | None
    year: int | None
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut | None = None
    qiraah: RecitationQiraahOut | None = None
    qualities: list[RecitationQualityOut] = []

    @staticmethod
    def resolve_qualities(obj):
        # Lets a consumer discover which ?quality= values this recitation accepts.
        return sorted_asset_qualities(obj)


class RecitationFilter(FilterSchema):
    id: Annotated[list[int] | None, FilterLookup(q="id__in")] = None
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    reciter_id: Annotated[list[int] | None, FilterLookup(q="reciter_id__in")] = None
    riwayah_id: Annotated[list[int] | None, FilterLookup(q="riwayah_id__in")] = None
    qiraah_id: Annotated[list[int] | None, FilterLookup(q="qiraah_id__in")] = None


@router.get("recitations/", response=list[RecitationListOut])
@track_search(SearchSurface.RECITATIONS)
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(
    search_fields=[
        "name",
        "description",
        "publisher__name",
        "reciter__name",
        "reciter__name_ar",
        "riwayah__name",
        "riwayah__name_ar",
        "qiraah__name",
        "qiraah__name_ar",
    ]
)
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("publisher")
    qs = service.get_all_recitations(publisher_q & Q(in_gallery=True), filters)

    return qs
