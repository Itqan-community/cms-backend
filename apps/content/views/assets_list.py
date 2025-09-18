from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class ListAssetPublisherOut(Schema):
    id: int
    name: str


class ListAssetOut(Schema):
    id: int
    category: str
    name: str
    description: str
    publisher: ListAssetPublisherOut = Field(alias="resource.publisher")
    license: str


class AssetFilter(FilterSchema):
    category: list[Asset.CategoryChoice] | None = Field(None, q="category__in")
    license_code: list[str] | None = Field(None, q="license__in")


@router.get("assets/", response=list[ListAssetOut], auth=None)
@paginate
@ordering(ordering_fields=["name", "category"])
@searching(search_fields=["name", "description", "resource__publisher__name", "category"])
def list_assets(request: Request, filters: AssetFilter = Query()):
    assets = Asset.objects.all()
    assets = filters.filter(assets)
    return assets
