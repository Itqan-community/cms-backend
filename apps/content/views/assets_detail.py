from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import Field

from apps.content.models import Asset
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class DetailAssetSnapshotOut(Schema):
    image_url: str
    title: str
    description: str


class DetailAssetPublisherOut(Schema):
    id: int
    name: str
    description: str


class DetailAssetOut(Schema):
    id: int
    category: str
    name: str
    description: str
    long_description: str
    thumbnail_url: str
    publisher: DetailAssetPublisherOut = Field(alias="resource.publisher")
    license: str
    snapshots: list[DetailAssetSnapshotOut] = Field(default_factory=list, alias="previews")


@router.get("assets/{id}/", response=DetailAssetOut, auth=None)
def detail_assets(request: Request, id: int):
    asset = get_object_or_404(Asset, id=id)
    return asset
