from django.utils import timezone

from apps.content.models import Asset, AssetAccess, AssetAccessRequest
from apps.users.models import User


def approve_request(
    asset_access_request: AssetAccessRequest,
    approved_by: User | None,
    admin_response: str,
):
    if asset_access_request.status != AssetAccessRequest.StatusChoice.PENDING:
        raise ValueError(f"Cannot approve request with status '{asset_access_request.status}'")

    asset_access_request.status = AssetAccessRequest.StatusChoice.APPROVED
    asset_access_request.approved_at = timezone.now()
    asset_access_request.approved_by = approved_by

    asset_access_request.admin_response = admin_response

    asset_access_request.save()

    access = AssetAccess.objects.create(
        asset_access_request=asset_access_request,
        user=asset_access_request.developer_user,
        asset=asset_access_request.asset,
        effective_license=asset_access_request.asset.license,
        expires_at=None,
    )  # maybe add download url and expiration logic later

    return access


def reject_request(asset_access_request: AssetAccessRequest, rejected_by_user=None, reason=""):
    if asset_access_request.status != AssetAccessRequest.StatusChoice.PENDING:
        raise ValueError(f"Cannot reject request with status '{asset_access_request.status}'")

    asset_access_request.status = AssetAccessRequest.StatusChoice.REJECTED
    asset_access_request.approved_at = timezone.now()
    asset_access_request.approved_by = rejected_by_user
    asset_access_request.admin_response = reason or "Request rejected"
    asset_access_request.save()


def request_access(
    user: User, asset: Asset, purpose: str, intended_use: str, auto_approve=True
) -> tuple[AssetAccessRequest, AssetAccess | None]:
    existing_request = AssetAccessRequest.objects.filter(developer_user=user, asset=asset).first()

    if existing_request:
        if existing_request.status == AssetAccessRequest.StatusChoice.APPROVED:
            access = getattr(existing_request, "access_grant", None)
            return existing_request, access
        elif existing_request.status == AssetAccessRequest.StatusChoice.PENDING:
            # Re-approve if auto_approve is enabled
            if auto_approve:
                access = approve_request(
                    existing_request,
                    approved_by=None,
                    admin_response="Automatically approved (V1 policy)",
                )
                return existing_request, access
            return existing_request, None

    request = AssetAccessRequest.objects.create(
        developer_user=user,
        asset=asset,
        developer_access_reason=purpose,
        intended_use=intended_use,
    )

    access = None
    if auto_approve:
        access = approve_request(
            request,
            approved_by=None,
            admin_response="Automatically approved (V1 policy)",
        )

    return request, access


def user_has_access(user: User, asset: Asset) -> bool:
    try:
        access = AssetAccess.objects.get(user=user, asset=asset)
        return access.is_active
    except AssetAccess.DoesNotExist:
        return False
