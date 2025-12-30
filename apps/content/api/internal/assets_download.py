import os
from typing import Literal

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from ninja import Schema
from rest_framework.exceptions import PermissionDenied

from apps.content.models import Asset, AssetAccess, UsageEvent
from apps.content.services.asset_access import user_has_access
from apps.content.tasks import create_usage_event_task
from apps.core.mixins.storage import generate_presigned_download_url
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class DownloadAssetOut(Schema):
    download_url: str


@router.get(
    "assets/{id}/download/",
    response={
        200: DownloadAssetOut,
        403: NinjaErrorResponse[Literal["permission_denied"], Literal[None]],
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_versions"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_available"], Literal[None]]
        | NinjaErrorResponse[Literal["file_not_accessible"], Literal[None]],
    },
)
def download_asset(request: Request, id: int):
    """
    Return a direct download URL for the latest asset version
    """
    # Get the asset
    asset = get_object_or_404(Asset, request.publisher_q("resource__publisher"), id=id)

    # Check if user has access using the service function
    if not user_has_access(request.user, asset):
        raise PermissionDenied(_("You do not have access to this asset"))

    # Get latest asset version
    asset_latest_version = asset.get_latest_version()
    if not asset_latest_version:
        raise Http404("No versions found for this asset")

    if not asset_latest_version.file_url:
        raise Http404("No file available for this asset")

    # Get download URL
    download_url = AssetAccess.objects.get(user=request.user, asset=asset).get_download_url()
    if not download_url:
        raise Http404("Download URL not available")

    # Generate pre-signed download url
    key = f"media/{asset_latest_version.file_url.name}"  # object key within the bucket
    filename = os.path.basename(key)
    download_url = generate_presigned_download_url(key=key, filename=filename, expires_in=3600)

    # Create usage event for file download
    create_usage_event_task.delay(
        {
            "developer_user_id": request.user.id,
            "usage_kind": UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            "subject_kind": UsageEvent.SubjectKindChoice.ASSET,
            "asset_id": asset.id,
            "resource_id": None,
            "metadata": {},
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.headers.get("User-Agent", ""),
            "effective_license": asset.license,
        }
    )

    return 200, DownloadAssetOut(download_url=download_url)
