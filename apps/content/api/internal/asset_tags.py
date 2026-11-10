from apps.content.asset_tag_schemas import AssetTagOut
from apps.content.models import AssetTag
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


@router.get("asset-tags/", response=list[AssetTagOut], auth=None)
def list_asset_tags(request: Request):
    """The text asset tags: the gallery filter and the portal's tag picker offer them."""
    return AssetTag.objects.all()
