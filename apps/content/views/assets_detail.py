from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import Field

from apps.content.models import Asset
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class DetailAssetPublisherOut(Schema):
    id: UUID
    name: str
    description: str


class DetailAssetLicenseOut(Schema):
    code: str
    name: str
    short_name: str


class DetailAssetOut(Schema):
    id: UUID
    category: str
    name: str
    description: str
    long_description: str
    thumbnail_url: str
    publisher: DetailAssetPublisherOut = Field(alias="resource.publisher")
    license: DetailAssetLicenseOut


@router.get("content/assets/{id}/", response=DetailAssetOut)
def detail_assets(request, id: UUID):
    asset = get_object_or_404(Asset, id=id)
    return asset
