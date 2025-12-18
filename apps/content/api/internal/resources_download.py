import os
from typing import Literal

from django.http import Http404
from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.content.models import Resource, UsageEvent
from apps.content.tasks import create_usage_event_task
from apps.core.mixins.storage import generate_presigned_download_url
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class DownloadResourceOut(Schema):
    download_url: str


@router.get(
    "resources/{id}/download/",
    response={
        200: DownloadResourceOut,
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_versions"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_available"], Literal[None]],
    },
)
def download_resource(request: Request, id: int):
    """
    Return a direct download URL for the latest resource version
    """
    # Get the resource
    resource = get_object_or_404(Resource, id=id)

    resource_latest_version = resource.get_latest_version()
    if not resource_latest_version:
        raise Http404("No versions found for this resource")

    if not resource_latest_version.storage_url:
        raise Http404("No file available for download")

    # Generate pre-signed download url
    key = resource_latest_version.storage_url.name  # object key within the bucket
    filename = os.path.basename(key)
    download_url = generate_presigned_download_url(key=key, filename=filename, expires_in=3600)

    # Create usage event for file download
    create_usage_event_task.delay(
        {
            "developer_user_id": request.user.id,
            "usage_kind": UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
            "subject_kind": UsageEvent.SubjectKindChoice.RESOURCE,
            "asset_id": None,
            "resource_id": resource.id,
            "metadata": {},
            "ip_address": request.META.get("REMOTE_ADDR"),
            "user_agent": request.headers.get("User-Agent", ""),
            "effective_license": resource.license,
        }
    )

    return DownloadResourceOut(download_url=download_url)
