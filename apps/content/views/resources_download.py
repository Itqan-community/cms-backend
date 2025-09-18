from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.content.models import Resource
from apps.content.models import ResourceVersion
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


@router.get("content/resources/{id}/download/")
def download_resource(request: Request, id: int):
    """
    Download the latest version of a resource.
    Returns the file directly for download.
    """
    # Get the resource
    resource = get_object_or_404(Resource, id=id)

    # Pick the latest by is_latest flag first, otherwise most recent by created_at
    latest_version = ResourceVersion.objects.filter(resource=resource).order_by("-is_latest", "-created_at").first()

    if not latest_version:
        raise Http404("No versions found for this resource")

    if not latest_version.storage_url:
        raise Http404("No file available for download")

    storage = latest_version.storage_url.storage
    name = latest_version.storage_url.name
    if not storage.exists(name):
        raise Http404("File not accessible: missing from storage")

    response = FileResponse(
        latest_version.storage_url.open("rb"),
        as_attachment=True,
        filename=f"{resource.name}_v{latest_version.semvar}.{latest_version.file_type}",
    )

    # Set content type based on file type
    content_types = {
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "zip": "application/zip",
    }

    if latest_version.file_type in content_types:
        response["Content-Type"] = content_types[latest_version.file_type]

    return response
