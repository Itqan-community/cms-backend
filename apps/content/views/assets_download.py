from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied
from typing import Literal

from apps.content.models import Asset, AssetVersion
from apps.content.services.asset_access import user_has_access
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.ASSETS])


@router.get(
    "content/assets/{id}/download/",
    response={
        403: NinjaErrorResponse[Literal["permission_denied"], Literal[None]],
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_versions"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_available"], Literal[None]]
        | NinjaErrorResponse[Literal["file_not_accessible"], Literal[None]]
    }
)
def download_asset(request: Request, id: int):
    """
    Download the latest version of an asset.
    Returns the file directly for download.
    """
    # Get the asset
    asset = get_object_or_404(Asset, id=id)
    
    # Check if user has access using the service function
    if not user_has_access(request.user, asset):
        raise PermissionDenied(_("You do not have access to this asset"))

    # Get the latest asset version with file
    latest_version = AssetVersion.objects.filter(
        asset=asset,
        file_url__isnull=False
    ).order_by("-created_at").first()

    if not latest_version:
        raise Http404("No file versions found for this asset")

    if not latest_version.file_url:
        raise Http404("No file available for download")

    storage = latest_version.file_url.storage
    name = latest_version.file_url.name
    if not storage.exists(name):
        raise Http404("File not accessible: missing from storage")

    # Get file extension for content type
    file_extension = name.split('.')[-1].lower() if '.' in name else ''
    
    response = FileResponse(
        latest_version.file_url.open("rb"),
        as_attachment=True,
        filename=f"{asset.name}_{latest_version.name}.{file_extension}",
    )

    # Set content type based on file extension
    content_types = {
        "csv": "text/csv",
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "json": "application/json",
        "xml": "application/xml",
        "zip": "application/zip",
        "tar": "application/x-tar",
        "gz": "application/gzip",
    }

    if file_extension in content_types:
        response["Content-Type"] = content_types[file_extension]

    return response
