from typing import Literal

from django.http import Http404
from django.shortcuts import get_object_or_404
from ninja import Schema
from rest_framework.response import Response
from rest_framework import status

from apps.content.models import Resource, ResourceVersion, UsageEvent
from apps.content.tasks import create_usage_event_task
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class DownloadResourceOut(Schema):
    download_url: str


@router.get(
    "resources/{id}/download/",
    response={
        200: DownloadResourceOut,
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_versions"], Literal[None]]
        | NinjaErrorResponse[Literal["no_file_available"], Literal[None]]
    }
)
def download_resource(request: Request, id: int):
    """
    Return a direct download URL for the latest resource version
    """
    # Get the resource
    resource = get_object_or_404(Resource, id=id)

    latest_version = resource.get_latest_version()
    if not latest_version:
        raise Http404("No versions found for this resource")

    if not latest_version.storage_url:
        raise Http404("No file available for download")

    # Create usage event for file download
    create_usage_event_task.delay({
        "developer_user_id": request.user.id,
        "usage_kind": UsageEvent.UsageKindChoice.FILE_DOWNLOAD,
        "subject_kind": UsageEvent.SubjectKindChoice.RESOURCE,
        "asset_id": None,
        "resource_id": resource.id,
        "metadata": {},
        "ip_address": request.META.get('REMOTE_ADDR'),
        "user_agent": request.headers.get('User-Agent', ''),
        "effective_license": resource.license
    })

    return DownloadResourceOut(download_url=latest_version.storage_url.url)
