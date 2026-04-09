from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate

from apps.content.models import Qiraah, Riwayah
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.FILTERS])


class QiraahFilterOut(Schema):
    id: int
    name: str
    bio: str


class RiwayahFilterOut(Schema):
    id: int
    name: str
    bio: str
    qiraah_id: int


class RiwayahFilterIn(FilterSchema):
    qiraah_id: int | None = None


@router.get("filters/qiraahs/", response=list[QiraahFilterOut])
@paginate
@searching(search_fields=["name_en", "name_ar"])
def list_qiraahs_for_filter(request: Request):
    """
    List qiraahs for use in dropdown filters.
    Searchable and paginated.
    """
    return Qiraah.objects.filter(is_active=True).order_by("name")


@router.get("filters/riwayahs/", response=list[RiwayahFilterOut])
@paginate
@searching(search_fields=["name_en", "name_ar"])
def list_riwayahs_for_filter(request: Request, filters: RiwayahFilterIn = Query(...)):
    """
    List riwayahs for use in dropdown filters.
    Searchable and paginated. Filterable by qiraah_id.
    """
    qs = Riwayah.objects.filter(is_active=True).order_by("name")
    qs = filters.filter(qs)
    return qs
