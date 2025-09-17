from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.content.models import Asset
from apps.content.services.asset_access import user_has_access
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class AssetAccessStatusOut(Schema):
    has_access: bool
    requires_approval: bool
    download_url: str | None


@router.get("content/assets/{asset_id}/access-status/", response=AssetAccessStatusOut)
def asset_access_status(request, asset_id: int):
    """Get asset access status for the authenticated user"""
    asset = get_object_or_404(Asset, id=asset_id)
    
    if not request.user.is_authenticated:
        return {
            "has_access": False,
            "requires_approval": False,  # V1: Auto-approval
            "download_url": None
        }
    
    # Check if user has access using the service function
    has_access = user_has_access(request.user, asset)
    download_url = None
    
    if has_access:
        # In a real implementation, this would generate a secure download URL
        download_url = f"/content/assets/{asset.id}/download/"
    
    return {
        "has_access": has_access,
        "requires_approval": False,  # V1: Auto-approval
        "download_url": download_url
    }
