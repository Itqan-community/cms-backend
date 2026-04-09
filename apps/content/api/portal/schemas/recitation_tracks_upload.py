from datetime import datetime
from typing import Literal

from ninja import Field, Schema

from apps.core.ninja_utils.router import ItqanRouter

# Kept to satisfy broad portal router autodiscovery.
router = ItqanRouter()


class ValidateUploadIn(Schema):
    asset_id: int
    filenames: list[str]


class UploadStartIn(Schema):
    asset_id: int
    filename: str
    duration_ms: int | None = None
    size_bytes: int | None = None


class UploadSignPartIn(Schema):
    key: str
    upload_id: str
    part_number: int


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


class UploadAbortIn(Schema):
    key: str
    upload_id: str


class ValidateFileOut(Schema):
    filename: str
    status: Literal["valid", "skip", "invalid"]


class ValidateUploadOut(Schema):
    asset_id: int
    status: Literal["valid", "invalid"]
    message: str
    files: list[ValidateFileOut]


class UploadStartOut(Schema):
    key: str
    upload_id: str
    content_type: str
    surah_number: int


class UploadSignPartOut(Schema):
    url: str


class UploadFinishOut(Schema):
    track_id: int
    asset_id: int
    surah_number: int
    size_bytes: int
    finished_at: datetime
    key: str


class UploadAbortOut(Schema):
    key: str
    upload_id: str
    aborted: bool
