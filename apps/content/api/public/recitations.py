from datetime import datetime

from ninja import Query, Schema
from ninja.pagination import paginate

from apps.content.api.internal.resources import RecitationFilter
from apps.content.models import Asset, Resource
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

# Base router for /developers-api/recitations
router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class ContentRecitationListOut(Schema):
    id: int
    resource_id: int
    name: str
    slug: str
    description: str
    reciter_id: int | None = None
    riwayah_id: int | None = None
    created_at: datetime
    updated_at: datetime


@router.get(
    "recitations/",
    response=list[ContentRecitationListOut],
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

    return qs
