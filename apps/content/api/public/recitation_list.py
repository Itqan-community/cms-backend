from django.db.models import Count, F
from django.db.models.functions import JSONObject
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, Resource
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationListOut(Schema):
    id: int
    name: str
    description: str
    publisher: dict = Field(validation_alias="publisher_dict")
    reciter: dict = Field(validation_alias="reciter_dict")
    riwayah: dict = Field(validation_alias="riwayah_dict")
    surahs_count: int


class RecitationFilter(FilterSchema):
    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request, filters: RecitationFilter = Query()):
    lang = request.LANGUAGE_CODE  # "ar" or "en"
    qs = Asset.objects.select_related(
        "resource", "resource__publisher", "reciter", "riwayah"
    ).filter(
        category=Asset.CategoryChoice.RECITATION,
        resource__category=Resource.CategoryChoice.RECITATION,
        resource__status=Resource.StatusChoice.READY,
    )

    qs = filters.filter(qs)
    qs = qs.annotate(
        surahs_count=Count("recitation_tracks", distinct=True),
        publisher_dict=JSONObject(
            id=F("resource__publisher__id"), name=F(f"resource__publisher__name_{lang}")
        ),
        reciter_dict=JSONObject(
            id=F("reciter__id"),
            name=F(f"reciter__name_{lang}"),
        ),
        riwayah_dict=JSONObject(
            id=F("riwayah__id"),
            name=F(f"riwayah__name_{lang}"),
        ),
    ).values(
        "id",
        "name",
        "description",
        "publisher_dict",
        "reciter_dict",
        "riwayah_dict",
        "surahs_count",
    )

    return qs
