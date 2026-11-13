"""How many assets the current publisher has of each type, for the portal home."""

from typing import Any

from django.db.models import Count, Q
from ninja import Schema

from apps.content.cache import PORTAL_ASSET_COUNTS_CACHE_TTL, portal_asset_counts_version
from apps.content.models import Asset, AssetTag, CategoryChoice, StatusChoice
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission, permission_class
from apps.core.permissions import PermissionChoice
from apps.usage_tracking.services.usage_reports import cached

router = ItqanRouter(tags=[NinjaTag.ASSETS])

# The categories that have a portal list, in the sidebar's order, with the permission that opens the list.
PORTAL_CATEGORY_PERMISSIONS: dict[CategoryChoice, PermissionChoice] = {
    CategoryChoice.TEXT: PermissionChoice.PORTAL_READ_TEXT_ASSET,
    CategoryChoice.MUSHAF: PermissionChoice.PORTAL_READ_MUSHAF,
    CategoryChoice.FONT: PermissionChoice.PORTAL_READ_FONT,
    CategoryChoice.RECITATION: PermissionChoice.PORTAL_READ_RECITATION,
}


class AssetTagCountOut(Schema):
    slug: str
    name: str
    total: int
    drafts: int


class AssetCategoryCountOut(Schema):
    category: CategoryChoice
    total: int
    drafts: int
    tags: list[AssetTagCountOut] = []


class AssetCountsOut(Schema):
    categories: list[AssetCategoryCountOut]


def _count_assets(scope: Q, tag_scope: Q) -> dict[str, Any]:
    """Two GROUP BY queries: assets per category, and text assets per tag. Drafts are counted too."""
    drafts = Q(status=StatusChoice.DRAFT)
    rows = (
        Asset.objects.filter(scope, category__in=list(PORTAL_CATEGORY_PERMISSIONS))
        .values("category")
        .annotate(total=Count("id"), drafts=Count("id", filter=drafts))
        .order_by()
    )
    by_category = {row["category"]: {"total": row["total"], "drafts": row["drafts"]} for row in rows}
    tags = (
        AssetTag.objects.filter(tag_scope, assets__category=CategoryChoice.TEXT)
        .annotate(total=Count("assets"), drafts=Count("assets", filter=Q(assets__status=StatusChoice.DRAFT)))
        .order_by("slug")
    )
    return {
        "categories": by_category,
        "tags": [{"slug": tag.slug, "name": tag.name, "total": tag.total, "drafts": tag.drafts} for tag in tags],
    }


@router.get("asset-counts/", response=AssetCountsOut)
@permission_required([permission_class(PermissionChoice.PORTAL_ACCESS)])
def asset_counts(request: Request):
    """Assets per type for the publisher in `X-Tenant` (every publisher for Itqan staff without it).

    Uses the same publisher scoping as the asset lists and lists only the types whose list the user
    may open. Drafts are included in `total` and also counted on their own. Text assets are also
    broken down by tag; an asset with two tags counts under both, an untagged one only in the total.
    Cached for a minute; creating, deleting or retagging an asset clears the cache.
    """
    scope = request.publisher_q()
    counts = cached(
        "portal-asset-counts",
        [scope.deconstruct(), portal_asset_counts_version()],
        lambda: _count_assets(scope, request.publisher_q("assets__publisher")),
        seconds=PORTAL_ASSET_COUNTS_CACHE_TTL,
    )
    categories = []
    for category, permission in PORTAL_CATEGORY_PERMISSIONS.items():
        if not check_permission(request.user, permission, publisher=request.publisher):
            continue
        row = counts["categories"].get(category, {"total": 0, "drafts": 0})
        tags = counts["tags"] if category == CategoryChoice.TEXT else []
        categories.append({"category": category, **row, "tags": tags})
    return {"categories": categories}
