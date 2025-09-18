from datetime import datetime
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field
from typing import Literal

from apps.content.models import Resource
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


class ListResourcePublisherOut(Schema):
    id: int
    name: str


class ListResourceOut(Schema):
    id: int
    category: str
    name: str
    description: str
    status: str
    publisher: ListResourcePublisherOut = Field(alias="publisher")
    created_at: datetime
    updated_at: datetime


class ResourceFilter(FilterSchema):
    category: list[Resource.CategoryChoice] | None = Field(None, q="category__in")
    status: list[Resource.StatusChoice] | None = Field(None, q="status__in")
    publisher_id: list[int] | None = Field(None, q="publisher_id__in")


# Input schemas for CRUD operations
class CreateResourceIn(Schema):
    name: str
    description: str
    category: Resource.CategoryChoice
    publisher_id: int


class UpdateResourceIn(Schema):
    name: str | None = None
    description: str | None = None
    category: Resource.CategoryChoice | None = None
    status: Resource.StatusChoice | None = None


class ResourceOut(Schema):
    id: int
    category: str
    name: str
    slug: str
    description: str
    status: str
    publisher_id: int
    created_at: datetime
    updated_at: datetime


# Detail view specific schemas
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
    created_at: datetime
    updated_at: datetime


# GET /content/resources/ - List resources with filtering, searching, ordering, and pagination
@router.get("content/resources/", response=list[ListResourceOut])
@paginate
@ordering(ordering_fields=["name", "category", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "publisher__name"])
def list_resources(request: Request, filters: ResourceFilter = Query()):
    resources = Resource.objects.select_related("publisher").all()
    resources = filters.filter(resources)
    return resources


# POST /content/resources/ - Create a new resource
@router.post("content/resources/", response=ResourceOut)
def create_resource(request: Request, data: CreateResourceIn):
    resource = Resource.objects.create(
        name=data.name,
        description=data.description,
        category=data.category,
        publisher_id=data.publisher_id
    )
    return resource


@router.put("content/resources/{id}/", response=ResourceOut)
def update_resource(request: Request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.patch("content/resources/{id}/", response=ResourceOut)
def partial_update_resource(request: Request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.delete("content/resources/{id}/")
def delete_resource(request: Request, id: int):
    resource = get_object_or_404(Resource, id=id)
    resource.delete()
    return {"success": True}


@router.post(
    "content/resources/{id}/publish/", 
    response={
        200: ResourceOut,
        400: NinjaErrorResponse[Literal["resource_already_published"], Literal[None]],
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
    }
)
def publish_resource(request: Request, id: int):
    resource = get_object_or_404(Resource, id=id)
    
    if resource.status == Resource.StatusChoice.READY:
        raise ItqanError("resource_already_published", _("Resource is already published"))
    
    resource.status = Resource.StatusChoice.READY
    resource.save()
    return resource


@router.post(
    "content/resources/{id}/unpublish/", 
    response={
        200: ResourceOut,
        400: NinjaErrorResponse[Literal["resource_already_unpublished"], Literal[None]],
        404: NinjaErrorResponse[Literal["not_found"], Literal[None]]
    }
)
def unpublish_resource(request: Request, id: int):
    resource = get_object_or_404(Resource, id=id)
    
    if resource.status == Resource.StatusChoice.DRAFT:
        raise ItqanError("resource_already_unpublished", _("Resource is already unpublished"))
    
    resource.status = Resource.StatusChoice.DRAFT
    resource.save()
    return resource


@router.get("content/resources/{id}/", response=DetailResourceOut)
def detail_resource(request: Request, id: int):
    resource = get_object_or_404(Resource.objects.select_related("publisher"), id=id)
    return resource
