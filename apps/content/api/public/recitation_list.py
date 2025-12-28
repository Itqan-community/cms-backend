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
    class RecitationPublisherOut(Schema):
        id: int
        name: str

    class RecitationReciterOut(Schema):
        id: int
        name: str

    class RecitationRiwayahOut(Schema):
        id: int
        name: str

    id: int
    name: str
    description: str
    publisher: RecitationPublisherOut
    reciter: RecitationReciterOut
    riwayah: RecitationRiwayahOut
    surahs_count: int

    @staticmethod
    def resolve_publisher(obj):
        publisher = obj.resource.publisher
        return {
            "id": publisher.id,
            "name": publisher.name,
        }  # modeltranslation chooses name_* based on active language

    @staticmethod
    def resolve_reciter(obj):
        return {"id": obj.reciter_id, "name": obj.reciter.name}

    @staticmethod
    def resolve_riwayah(obj):
        return {"id": obj.riwayah_id, "name": obj.riwayah.name}

    @staticmethod
    def resolve_surahs_count(obj):
        return obj.recitation_tracks.count()


class RecitationFilter(FilterSchema):
    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")


@router.get("recitations/", response=list[RecitationListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request, filters: RecitationFilter = Query()):
    qs = Asset.objects.select_related(
        "resource", "resource__publisher", "reciter", "riwayah"
    ).filter(
        category=Asset.CategoryChoice.RECITATION,
        resource__category=Resource.CategoryChoice.RECITATION,
        resource__status=Resource.StatusChoice.READY,
    )

    qs = filters.filter(qs)
    return qs
