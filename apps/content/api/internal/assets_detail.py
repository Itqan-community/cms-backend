from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import Field, field_serializer
from pydantic_core.core_schema import SerializationInfo

from apps.content.models import Asset, UsageEvent
from apps.content.tasks import create_usage_event_task
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.mixins.helpers import run_task

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class DetailAssetSnapshotOut(Schema):
    image_url: str | None
    title: str
    description: str

    @field_serializer("image_url")
    def serialize_image_url(self, value, info: SerializationInfo) -> str:
        request = info.context.get("request") if info.context else None
        if request and isinstance(value, str) and not value.startswith("https"):
            return request.build_absolute_uri(value)

        return value if isinstance(value, str) else ""


class DetailAssetPublisherOut(Schema):
    id: int
    name: str
    description: str


class DetailAssetResourceOut(Schema):
    id: int


class DetailAssetOut(Schema):
    id: int
    category: str
    name: str
    description: str
    long_description: str
    thumbnail_url: str | None
    publisher: DetailAssetPublisherOut = Field(alias="resource.publisher")
    resource: DetailAssetResourceOut
    license: str
    snapshots: list[DetailAssetSnapshotOut] = Field(default_factory=list, alias="previews")

    @field_serializer("thumbnail_url")
    def serialize_thumbnail_url(self, value, info: SerializationInfo) -> str:
        request = info.context.get("request") if info.context else None
        if request and isinstance(value, str) and not value.startswith("https"):
            return request.build_absolute_uri(value)

        return value if isinstance(value, str) else ""


@router.get("assets/{id}/", response=DetailAssetOut, auth=None)
def detail_assets(request: Request, id: int):
    asset = get_object_or_404(Asset, request.publisher_q("resource__publisher"), id=id)

    # Only create usage event for authenticated users
    if hasattr(request, "user") and request.user and request.user.is_authenticated:
        run_task(
            create_usage_event_task,
            {
                "developer_user_id": request.user.id,
                "usage_kind": UsageEvent.UsageKindChoice.VIEW,
                "subject_kind": UsageEvent.SubjectKindChoice.ASSET,
                "asset_id": asset.id,
                "resource_id": None,
                "metadata": {},
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.headers.get("User-Agent", ""),
                "effective_license": asset.license,
            },
        )

    return asset
