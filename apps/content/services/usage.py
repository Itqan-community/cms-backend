from dotenv.variables import Literal

from apps.content.models import AssetAccess, UsageEvent


def create_usage_event(
    asset_access: AssetAccess,
    usage_kind=Literal["file_download"],
    ip_address=None,
    user_agent: str = "",
):
    """
    Create a usage event when the asset is accessed.
    """

    return UsageEvent.objects.create(
        developer_user=asset_access.user,
        usage_kind=usage_kind,
        subject_kind="asset",
        asset_id=asset_access.asset.id,
        metadata={
            "asset_name": asset_access.asset.name,
            "file_size": asset_access.asset.file_size,
            "format": asset_access.asset.format,
            "license": asset_access.effective_license,
            "access_id": asset_access.id,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_asset_view(
    user, asset, *, ip_address=None, user_agent=""
):  # Add * to make ip_address and user_agent keyword-only
    """Track asset view event"""
    return UsageEvent.objects.create(
        developer_user=user,
        usage_kind="view",
        subject_kind="asset",
        asset_id=asset.id,
        metadata={"asset_title": asset.title, "category": asset.category},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_resource_download(user, resource, ip_address=None, user_agent=""):
    """Track resource download event"""
    latest_version = resource.get_latest_version()
    return UsageEvent.objects.create(
        developer_user=user,
        usage_kind="file_download",
        subject_kind="resource",
        resource_id=resource.id,
        metadata={
            "resource_name": resource.name,
            "version": latest_version.semvar if latest_version else "unknown",
            "category": resource.category,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_api_access(
    user, *, api_endpoint="", ip_address=None, user_agent="", resource=None, asset=None
) -> None:
    """Track API access event"""
    if resource:
        return UsageEvent.objects.create(
            developer_user=user,
            usage_kind="api_access",
            subject_kind="resource",
            resource_id=resource.id,
            metadata={"api_endpoint": api_endpoint, "resource_name": resource.name},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    elif asset:
        return UsageEvent.objects.create(
            developer_user=user,
            usage_kind="api_access",
            subject_kind="asset",
            asset_id=asset.id,
            metadata={"api_endpoint": api_endpoint, "asset_title": asset.title},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    return None


def log_asset_download(user, asset, ip_address=None, user_agent=""):
    """Track asset download event with async processing"""

    try:
        from .tasks import track_event_async

        event_data = {
            "developer_user_id": user.id,
            "usage_kind": "file_download",
            "subject_kind": "asset",
            "asset_id": asset.id,
            "metadata": {
                "asset_title": asset.title,
                "file_size": asset.file_size,
                "format": asset.format,
                "category": asset.category,
            },
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        if track_event_async(event_data):
            return None  # Event queued for async processing
    except ImportError:
        pass

    # Fallback to synchronous creation
    return UsageEvent.objects.create(
        developer_user=user,
        usage_kind="file_download",
        subject_kind="asset",
        asset_id=asset.id,
        metadata={
            "asset_title": asset.title,
            "file_size": asset.file_size,
            "format": asset.format,
            "category": asset.category,
        },
        ip_address=ip_address,
        user_agent=user_agent,
    )
