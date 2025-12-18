from datetime import datetime

from django.db.models import F
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, Resource
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationListOut(Schema):
    id: int
    resource_id: int
    name: str
    slug: str
    description: str
    reciter_id: int | None = None
    riwayah_id: int | None = None
    created_at: datetime
    updated_at: datetime


class RecitationFilter(FilterSchema):
    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")


@router.get(
    "recitations/",
    response=list[RecitationListOut],
    auth=None,
)
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request, filters: RecitationFilter = Query()):
    qs = Asset.objects.select_related("resource", "reciter").filter(
        category=Asset.CategoryChoice.RECITATION,
        resource__category=Resource.CategoryChoice.RECITATION,
        resource__status=Resource.StatusChoice.READY,
    )

    qs = filters.filter(qs)

    # Ensure required slug comes from related Resource. Temp solution until we add slug to Asset model.
    qs = qs.annotate(slug=F("resource__slug"))

    return qs
