from ninja import Schema
from ninja.pagination import paginate

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.FILTERS])


class PublisherFilterOut(Schema):
    id: int
    name: str


@router.get("filters/publishers/", response=list[PublisherFilterOut])
@paginate
@searching(search_fields=["name_en", "name_ar"])
def list_publishers_for_filter(request: Request):
    """
    List publishers for use in dropdown filters.
    Searchable and paginated.
    """
    qs = Publisher.objects.all().order_by("name")
    return qs
