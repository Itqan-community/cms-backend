from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import Field

from apps.content.models import Asset, UsageEvent
from apps.content.tasks import create_usage_event_task
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class DetailAssetSnapshotOut(Schema):
    image_url: str | None
    title: str
    description: str


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


@router.get("assets/{id}/", response=DetailAssetOut, auth=None)
def detail_assets(request: Request, id: int):
    asset = get_object_or_404(Asset, id=id)
    
    # Only create usage event for authenticated users
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        create_usage_event_task.delay({
            "developer_user_id": request.user.id,
            "usage_kind": UsageEvent.UsageKindChoice.VIEW,
            "subject_kind": UsageEvent.SubjectKindChoice.ASSET,
            "asset_id": asset.id,
            "resource_id": None,
            "metadata": {},
            "ip_address": request.META.get('REMOTE_ADDR'),
            "user_agent": request.headers.get('User-Agent', ''),
            "effective_license": asset.license
        })
    
    return asset
