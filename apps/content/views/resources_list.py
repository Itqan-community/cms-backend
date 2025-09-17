from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Resource
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class ListResourcePublisherOut(Schema):
    id: int
    name: str


class ListResourceOut(Schema):
    id: int
    category: str
    name: str
    description: str
    status: str
    publisher: ListResourcePublisherOut = Field(alias="publisher")
    created_at: str
    updated_at: str


class ResourceFilter(FilterSchema):
    category: list[Resource.CategoryChoice] | None = Field(None, q="category__in")
    status: list[Resource.StatusChoice] | None = Field(None, q="status__in")
    publisher_id: list[int] | None = Field(None, q="publisher_id__in")


@router.get("content/resources/", response=list[ListResourceOut])
@paginate
@ordering(ordering_fields=["name", "category", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "publisher__name"])
def list_resources(request, filters: ResourceFilter = Query()):
    resources = Resource.objects.select_related("publisher").all()
    resources = filters.filter(resources)
    return resources
