from typing import Literal

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile

from apps.content.models import Asset
from apps.content.services.admin.asset_recitation_ayah_timestamps_upload_service import (
    ResultDict,
    bulk_upload_recitation_ayah_timestamps,
)
from apps.content.services.admin.asset_recitation_json_file_sync_service import sync_asset_recitations_json_file
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class TimingUploadIn(Schema):
    asset_id: int


class TimingUploadOut(Schema):
    asset_id: int
    created_total: int
    updated_total: int
    skipped_total: int
    missing_tracks: list[int]
    file_errors: list[str]
    synced_file_url: str | None
    synced_filename: str


@router.post(
    "timing/upload/",
    response={
        200: TimingUploadOut,
        400: NinjaErrorResponse[Literal["upload_failed"], ResultDict] | NinjaErrorResponse[Literal["no_asset_version"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
    },
)
def upload_timing(
    request: Request,
    data: Form[TimingUploadIn],
    files: list[UploadedFile] = File(...),
):
    try:
        asset = Asset.objects.get(pk=data.asset_id)
    except Asset.DoesNotExist:
        raise ItqanError(
            error_name="asset_not_found",
            message=_("Asset with id %s does not exist.") % data.asset_id,
            status_code=404,
        ) from None

    with transaction.atomic():
        stats = bulk_upload_recitation_ayah_timestamps(asset_id=asset.id, files=files)

        if stats["file_errors"]:
            raise ItqanError(
                error_name="upload_failed",
                message=_("One or more timing files could not be processed."),
                status_code=400,
                extra=stats,
            )

        try:
            asset_version, filename = sync_asset_recitations_json_file(asset_id=asset.id)
        except ValueError as exc:
            raise ItqanError(
                error_name="no_asset_version",
                message=_("This asset has no version to sync the recitation data into."),
                status_code=400,
            ) from exc

    synced_file_url = asset_version.file_url.url if asset_version.file_url else None

    return TimingUploadOut(
        asset_id=asset.id,
        created_total=stats["created_total"],
        updated_total=stats["updated_total"],
        skipped_total=stats["skipped_total"],
        missing_tracks=stats["missing_tracks"],
        file_errors=stats["file_errors"],
        synced_file_url=synced_file_url,
        synced_filename=filename,
    )
