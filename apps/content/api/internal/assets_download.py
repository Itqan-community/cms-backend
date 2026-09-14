import logging
import os
from typing import Literal

from django.conf import settings
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
logger = logging.getLogger(__name__)


class DownloadAssetOut(Schema):
    download_url: str


@router.get(
    "assets/{id}/download/",
    response={
        200: DownloadAssetOut,
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["not_found"]]
        | NinjaErrorResponse[Literal["no_file_versions"]]
        | NinjaErrorResponse[Literal["no_file_available"]]
        | NinjaErrorResponse[Literal["language_not_available"]]
        | NinjaErrorResponse[Literal["file_not_accessible"]],
    },
)
def download_asset(request: Request, id: int, language: str | None = None):
    """
    Return a direct download URL for the latest asset version.

    ``language`` selects a specific language rendition of a multi-language asset;
    when omitted the asset's source language is served (backward compatible).
    """
    # Get the asset
    asset = get_object_or_404(Asset, request.publisher_q("publisher"), restricted_for_tenant=False, id=id)

    # Check if user has access using the service function
    if not user_has_access(request.user, asset):
        raise PermissionDenied(_("You do not have access to this asset"))

    if language is not None and not asset.languages.filter(language=language).exists():
        raise Http404(str(_("Language not available for this asset")))

    # Get latest asset version (of the requested language, or the source language)
    asset_latest_version = asset.get_latest_version(language)
    if not asset_latest_version:
        raise Http404(str(_("No versions found for this asset")))

    if not asset_latest_version.file_url:
        raise Http404(str(_("No file available for this asset")))

    if not asset.is_open_access:
        download_url = AssetAccess.objects.get(user=request.user, asset=asset).get_download_url()
        if not download_url:
            raise Http404(str(_("Download URL not available")))

    if settings.CLOUDFLARE_R2_ENDPOINT:
        # Object storage (staging/prod): hand out a short-lived pre-signed URL.
        key = f"media/{asset_latest_version.file_url.name}"  # object key within the bucket
        filename = os.path.basename(key)
        download_url = generate_presigned_download_url(key=key, filename=filename, expires_in=3600)
    else:
        # Local/dev without object storage: serve the file via its media URL so
        # downloads work without R2. Prod/staging keep the pre-signed flow above.
        download_url = request.build_absolute_uri(asset_latest_version.file_url.url)

    # Create usage event for file download
    create_usage_event_task.delay(
        {
            "developer_user_id": request.user.id,
            "usage_kind": UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            "asset_id": asset.id,
            "metadata": (
                {"language": asset_latest_version.asset_language.language}
                if asset_latest_version.asset_language_id
                else {}
            ),
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.headers.get("User-Agent", ""),
            "effective_license": asset.license,
        }
    )

    logger.info(f"Asset download initiated [asset_id={id}, user_id={request.user.id}]")
    return 200, DownloadAssetOut(download_url=download_url)
