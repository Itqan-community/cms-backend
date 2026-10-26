import logging
from typing import Annotated

from django.db.models import Exists, OuterRef
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    CategoryChoice,
    LicenseChoice,
    RecitationAyahTiming,
    StatusChoice,
    consumer_visible_q,
)
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.usage_tracking.decorators.track_search import track_search
from apps.usage_tracking.models import SearchSurface

router = ItqanRouter(tags=[NinjaTag.ASSETS])
logger = logging.getLogger(__name__)


class ListAssetPublisherOut(Schema):
    id: int
    name: str


class ListAssetReciterOut(Schema):
    id: int
    name: str


class AssetMushafLayoutOut(Schema):
    id: int
    name: str
    page_count: int


class ListAssetOut(Schema):
    id: int
    category: str
    name: str
    description: str
    publisher: ListAssetPublisherOut = Field(alias="publisher")
    reciter: ListAssetReciterOut | None = None
    license: LicenseChoice
    is_open_access: bool
    template: AssetTemplateChoice | None = None
    mushaf_layout: AssetMushafLayoutOut | None = None
    has_ayah_timings: bool


class AssetFilter(FilterSchema):
    category: Annotated[list[CategoryChoice] | None, FilterLookup(q="category__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    publisher_id: Annotated[int | None, FilterLookup(q="publisher")] = None
    reciter_id: Annotated[int | None, FilterLookup(q="reciter")] = None
    is_open_access: Annotated[bool | None, FilterLookup(q="is_open_access")] = None


@router.get("assets/", response=list[ListAssetOut], auth=None)
@track_search(SearchSurface.ASSETS)
@paginate
@ordering(ordering_fields=["name", "category"])
@searching(search_fields=["name", "description", "publisher__name", "category"])
def list_assets(request: Request, filters: AssetFilter = Query()):
    """
    Retrieve a paginated list of assets for the internal CMS.
    Optimized with select_related for publisher and reciter to prevent N+1 queries.
    """
    logger.info("Assets list requested")
    assets = (
        Asset.objects.select_related("publisher", "reciter", "mushaf_layout")
        .filter(request.publisher_q("publisher"))
        .filter(restricted_for_tenant=False)
        .exclude(status=StatusChoice.DRAFT)
        .filter(consumer_visible_q())
        .annotate(
            # Only folders consumers can see count; a hidden folder's timings are withdrawn.
            has_ayah_timings=Exists(
                RecitationAyahTiming.objects.filter(track__asset=OuterRef("pk"), track__folder__is_visible=True)
            )
        )
    )
    assets = filters.filter(assets)
    return assets
