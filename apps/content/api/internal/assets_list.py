import logging
from typing import Annotated

from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import Asset, CategoryChoice, LicenseChoice, StatusChoice
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])
logger = logging.getLogger(__name__)


class ListAssetPublisherOut(Schema):
    id: int
    name: str


class ListAssetOut(Schema):
    id: int
    category: str
    name: str
    description: str
    publisher: ListAssetPublisherOut = Field(alias="publisher")
    license: LicenseChoice


class AssetFilter(FilterSchema):
    category: Annotated[list[CategoryChoice] | None, FilterLookup(q="category__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    publisher_id: Annotated[int | None, FilterLookup(q="publisher")] = None


@router.get("assets/", response=list[ListAssetOut], auth=None)
@paginate
@ordering(ordering_fields=["name", "category"])
@searching(search_fields=["name", "description", "publisher__name", "category"])
def list_assets(request: Request, filters: AssetFilter = Query()):
    logger.info("Assets list requested")
    assets = Asset.objects.filter(request.publisher_q("publisher")).exclude(status=StatusChoice.DRAFT)
    assets = filters.filter(assets)
    return assets
