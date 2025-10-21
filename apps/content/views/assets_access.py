from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import AwareDatetime

from apps.content.models import Asset, AssetAccessRequest
from apps.content.services.asset_access import request_access, user_has_access
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class RequestAccessIn(Schema):
    purpose: str
    intended_use: AssetAccessRequest.IntendedUseChoice


class AccessRequestOut(Schema):
    id: int
    asset_id: int
    purpose: str
    intended_use: str
    status: str
    created_at: AwareDatetime


class AccessGrantOut(Schema):
    id: int
    asset_id: int
    expires_at: AwareDatetime | None
    is_active: bool


class AccessRequestResponseOut(Schema):
    request: AccessRequestOut
    access: AccessGrantOut | None


@router.post("assets/{asset_id}/request-access/", response=AccessRequestResponseOut)
def request_asset_access(request: Request, asset_id: int, data: RequestAccessIn):
    """Request access to an asset (V1: auto-approval)"""
    asset = get_object_or_404(Asset, id=asset_id)
    
    # Validation is now handled by the schema using IntendedUseChoice
    # No need for manual validation since Django Ninja will validate the enum
    
    # Use the service function to handle access request
    access_request, access_grant = request_access(
        user=request.user,
        asset=asset,
        purpose=data.purpose,
        intended_use=data.intended_use,
        auto_approve=True  # V1: Auto-approval
    )
    
    return {
        "request": {
            "id": access_request.id,
            "asset_id": asset.id,
            "purpose": access_request.developer_access_reason,
            "intended_use": access_request.intended_use,
            "status": access_request.status,
            "created_at": access_request.created_at
        },
        "access": {
            "id": access_grant.id if access_grant else 0,
            "asset_id": asset.id,
            "expires_at": access_grant.expires_at if access_grant else None,
            "is_active": access_grant.is_active if access_grant else False
        } if access_grant else None
    }
