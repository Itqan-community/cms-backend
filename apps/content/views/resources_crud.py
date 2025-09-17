from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from ninja import Schema
from pydantic import Field
from typing import Literal

from apps.content.models import Resource
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RESOURCES])


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
    created_at: str
    updated_at: str


@router.post("content/resources/", response=ResourceOut)
def create_resource(request, data: CreateResourceIn):
    resource = Resource.objects.create(
        name=data.name,
        description=data.description,
        category=data.category,
        publisher_id=data.publisher_id
    )
    return resource


@router.put("content/resources/{id}/", response=ResourceOut)
def update_resource(request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.patch("content/resources/{id}/", response=ResourceOut)
def partial_update_resource(request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.delete("content/resources/{id}/")
def delete_resource(request, id: int):
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
def publish_resource(request, id: int):
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
def unpublish_resource(request, id: int):
    resource = get_object_or_404(Resource, id=id)
    
    if resource.status == Resource.StatusChoice.DRAFT:
        raise ItqanError("resource_already_unpublished", _("Resource is already unpublished"))
    
    resource.status = Resource.StatusChoice.DRAFT
    resource.save()
    return resource
