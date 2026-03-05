from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherListOut(Schema):
    id: int
    name: str
    slug: str
    is_verified: bool
    country: str
    foundation_year: int | None
    created_at: str

    @staticmethod
    def resolve_created_at(obj: Publisher) -> str:
        return obj.created_at.isoformat() if obj.created_at else ""


class PublisherListFilter(FilterSchema):
    is_verified: bool | None = Field(None, q="is_verified")
    country: str | None = Field(None, q="country")


@router.get("publishers/", response=list[PublisherListOut])
@paginate
@ordering(ordering_fields=["name", "created_at"])
@searching(search_fields=["name", "name_ar", "description", "description_ar"])
def list_publishers(request: Request, filters: PublisherListFilter = Query()):
    qs = Publisher.objects.all().order_by("-created_at")
    qs = filters.filter(qs)
    return qs
