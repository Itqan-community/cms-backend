from django.db.models import Count, Q
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, Reciter, Resource
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter

from apps.core.ninja_utils.tags import NinjaTag

# Base router for /developers-api/reciters
router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class ContentReciterOut(Schema):
    id: int
    slug: str
    name: str
    name_ar: str
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this reciter",
    )


@router.get("reciters/", response=list[ContentReciterOut], auth=None)
@paginate
@ordering(ordering_fields=["name", "name_ar", "slug"])
def list_content_reciters(request: Request):
    """
    Public Content API (V2):

    List reciters that have at least one READY recitation Asset.

    Conditions:
    - Reciter.is_active = True
    - Asset.category = RECITATION
    - Asset.reciter = this Reciter
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    """

    recitation_filter = Q(
        assets__category=Asset.CategoryChoice.RECITATION,
        assets__reciter__isnull=False,
        assets__resource__category=Resource.CategoryChoice.RECITATION,
        assets__resource__status=Resource.StatusChoice.READY,
    )

    qs = (
        Reciter.objects.filter(
            is_active=True,
        )
        .filter(recitation_filter)
        .distinct()
        .annotate(
            recitations_count=Count(
                "assets",
                filter=recitation_filter,
            )
        )
        .order_by("name")
    )

    return qs
