from datetime import datetime
from typing import Literal

from ninja import Schema
from pydantic import Field
from rest_framework.generics import get_object_or_404

from apps.content.models import Asset
from apps.content.services.admin.asset_recitation_audio_tracks_direct_upload_service import (
    AssetRecitationAudioTracksDirectUploadService,
)
from apps.content.services.validate_recitation_tracks_upload_service import ValidateRecitationTracksUploadService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class ValidateFileOut(Schema):
    filename: str
    status: Literal["valid", "skip", "invalid"]


class ValidateUploadIn(Schema):
    asset_id: int
    filenames: list[str]


class ValidateUploadOut(Schema):
    asset_id: int
    status: Literal["valid", "invalid"]
    message: str
    files: list[ValidateFileOut]


@router.post(
    "recitation-tracks/validate-upload/",
    response={
        200: ValidateUploadOut,
        400: NinjaErrorResponse[Literal["validation_error"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
    ]
)
def validate_upload(request: Request, data: ValidateUploadIn):

    asset = get_object_or_404(Asset, id=data.asset_id)

    service = ValidateRecitationTracksUploadService()
    result = service.validate(asset_id=asset.id, filenames=data.filenames)

    return ValidateUploadOut(
        asset_id=result.asset_id,
        status=result.status,
        message=result.message,
        files=[ValidateFileOut(filename=f.filename, status=f.status) for f in result.files],
    )


class UploadStartIn(Schema):
    asset_id: int
    filename: str
    duration_ms: int | None = None
    size_bytes: int | None = None


class UploadStartOut(Schema):
    key: str
    upload_id: str
    content_type: str
    surah_number: int


@router.post(
    "recitation-tracks/uploads/start/",
    response={
        200: UploadStartOut,
        400: NinjaErrorResponse[Literal["duplicate_track"]]
        | NinjaErrorResponse[Literal["invalid_filename"]]
        | NinjaErrorResponse[Literal["invalid_surah_number"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
        409: NinjaErrorResponse[Literal["duplicate_track"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
    ]
)
def start_upload(request: Request, data: UploadStartIn):

    asset = get_object_or_404(Asset, id=data.asset_id)

    service = AssetRecitationAudioTracksDirectUploadService()
    result = service.start_upload(asset_id=asset.id, filename=data.filename)

    return UploadStartOut(
        key=result["key"],
        upload_id=result["uploadId"],
        content_type=result["contentType"],
        surah_number=result["surahNumber"],
    )


class UploadSignPartIn(Schema):
    key: str
    upload_id: str
    part_number: int


class UploadSignPartOut(Schema):
    url: str


@router.post(
    "recitation-tracks/uploads/sign-part/",
    response={
        200: UploadSignPartOut,
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
    ]
)
def sign_part(request: Request, data: UploadSignPartIn):

    service = AssetRecitationAudioTracksDirectUploadService()
    result = service.sign_part(key=data.key, upload_id=data.upload_id, part_number=data.part_number)

    return UploadSignPartOut(url=result["url"])


class UploadPartIn(Schema):
    etag: str = Field(alias="ETag")
    part_number: int = Field(alias="PartNumber")


class UploadFinishIn(Schema):
    asset_id: int
    filename: str
    key: str
    upload_id: str
    parts: list[UploadPartIn]
    duration_ms: int | None = None
    size_bytes: int | None = None


class UploadFinishOut(Schema):
    track_id: int
    asset_id: int
    surah_number: int
    size_bytes: int
    finished_at: datetime
    key: str


@router.post(
    "recitation-tracks/uploads/finish/",
    response={
        200: UploadFinishOut,
        400: NinjaErrorResponse[Literal["duplicate_track"]]
        | NinjaErrorResponse[Literal["invalid_filename"]]
        | NinjaErrorResponse[Literal["invalid_surah_number"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["asset_not_found"]],
        409: NinjaErrorResponse[Literal["duplicate_track"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
    ]
)
def finish_upload(request: Request, data: UploadFinishIn):

    asset = get_object_or_404(Asset, id=data.asset_id)

    service = AssetRecitationAudioTracksDirectUploadService()
    result = service.finish_upload(
        key=data.key,
        upload_id=data.upload_id,
        parts=[part.model_dump(by_alias=True) for part in data.parts],
        asset_id=asset.id,
        filename=data.filename,
        duration_ms=data.duration_ms,
        size_bytes=data.size_bytes,
    )

    return UploadFinishOut(
        track_id=result["trackId"],
        asset_id=result["assetId"],
        surah_number=result["surahNumber"],
        size_bytes=result["sizeBytes"],
        finished_at=result["finishedAt"],
        key=result["key"],
    )


class UploadAbortIn(Schema):
    key: str
    upload_id: str


class UploadAbortOut(Schema):
    key: str
    upload_id: str
    aborted: bool


@router.post(
    "recitation-tracks/uploads/abort/",
    response={
        200: UploadAbortOut,
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
    },
)
@permission_required(
    [
        permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)
        | permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)
    ]
)
def abort_upload(request: Request, data: UploadAbortIn):

    service = AssetRecitationAudioTracksDirectUploadService()
    result = service.abort_upload(key=data.key, upload_id=data.upload_id)

    return UploadAbortOut(key=data.key, upload_id=data.upload_id, aborted=result["aborted"])
