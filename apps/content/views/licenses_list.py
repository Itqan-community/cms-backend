from uuid import UUID

from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import License
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.LICENSES])


class ListLicenseOut(Schema):
    id: UUID
    code: str
    name: str
    short_name: str
    is_default: bool


class LicenseFilter(FilterSchema):
    code: list[str] | None = Field(None, q="code__in")
    is_default: bool | None = None


@router.get("content/licenses/", response=list[ListLicenseOut])
@paginate
@ordering(ordering_fields=["code", "name", "short_name"])
@searching(search_fields=["code", "name", "short_name"])
def list_licenses(request, filters: LicenseFilter = Query()):
    queryset = License.objects.all()
    queryset = filters.filter(queryset)
    return queryset
