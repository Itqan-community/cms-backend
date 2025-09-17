from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import Field

from apps.content.models import Resource
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class DetailResourcePublisherOut(Schema):
    id: int
    name: str
    description: str


class DetailResourceOut(Schema):
    id: int
    category: str
    name: str
    slug: str
    description: str
    status: str
    publisher: DetailResourcePublisherOut = Field(alias="publisher")
    created_at: str
    updated_at: str


@router.get("content/resources/{id}/", response=DetailResourceOut)
def detail_resources(request, id: int):
    resource = get_object_or_404(Resource.objects.select_related("publisher"), id=id)
    return resource
