from uuid import UUID

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

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class ListAssetPublisherOut(Schema):
    id: UUID
    name: str


class ListAssetLicenseOut(Schema):
    code: str
    short_name: str


class ListAssetOut(Schema):
    id: UUID
    category: str
    name: str
    description: str
    publisher: ListAssetPublisherOut = Field(alias="resource.publisher")
    license: ListAssetLicenseOut


class AssetFilter(FilterSchema):
    category: list[Asset.CategoryChoice] | None = Field(None, q="category__in")
    license_code: str | list[str] | None = Field(None, q="license__code")


@router.get("content/assets/", response=list[ListAssetOut])
@paginate
@ordering(ordering_fields=["name", "category"])
@searching(search_fields=["name", "description", "resource__publisher__name", "category"])
def list_assets(request, filters: AssetFilter = Query()):
    assets = Asset.objects.all()
    assets = filters.filter(assets)
    return assets
