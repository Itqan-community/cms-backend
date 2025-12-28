from django.db.models import Count, Q
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, Resource, Riwayah
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RIWAYAHS])


class RiwayahOut(Schema):
    id: int
    slug: str
    name: str
    name_ar: str
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this riwayah",
    )


@router.get("riwayahs/", response=list[RiwayahOut])
@paginate
@ordering(ordering_fields=["name", "name_ar", "slug"])
def list_riwayahs(request: Request):
    """
    Public Content API (V2):

    List riwayahs that have at least one READY recitation Asset.

    Conditions:
    - Riwayah.is_active = True
    - Asset.category = RECITATION
    - Asset.riwayah = this Riwayah
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    """

    recitation_filter = Q(
        assets__category=Asset.CategoryChoice.RECITATION,
        assets__riwayah__isnull=False,
        assets__resource__category=Resource.CategoryChoice.RECITATION,
        assets__resource__status=Resource.StatusChoice.READY,
    )

    qs = (
        Riwayah.objects.filter(
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
