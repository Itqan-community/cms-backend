from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import FilterSchema
from ninja import Query
from ninja import Schema
from ninja.pagination import paginate
from pydantic import Field
from pydantic import AwareDatetime

from apps.content.models import Resource, UsageEvent
from apps.content.tasks import create_usage_event_task
from apps.core.ninja_utils.auth import ninja_jwt_auth_optional
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

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
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ResourceFilter(FilterSchema):
    category: list[Resource.CategoryChoice] | None = Field(None, q="category__in")
    status: list[Resource.StatusChoice] | None = Field(None, q="status__in")
    publisher_id: list[int] | None = Field(None, q="publisher_id__in")


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
    created_at: AwareDatetime
    updated_at: AwareDatetime


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
    created_at: AwareDatetime
    updated_at: AwareDatetime


@router.get("resources/", response=list[ListResourceOut])
@paginate
@ordering(ordering_fields=["name", "category", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "publisher__name"])
def list_resources(request: Request, filters: ResourceFilter = Query()):
    resources = Resource.objects.select_related("publisher").all()
    resources = filters.filter(resources)
    return resources


@router.post("resources/", response=ResourceOut)
def create_resource(request: Request, data: CreateResourceIn):
    resource = Resource.objects.create(
        name=data.name,
        description=data.description,
        category=data.category,
        publisher_id=data.publisher_id
    )
    return resource


@router.put("resources/{id}/", response=ResourceOut)
def update_resource(request: Request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.patch("resources/{id}/", response=ResourceOut)
def partial_update_resource(request: Request, id: int, data: UpdateResourceIn):
    resource = get_object_or_404(Resource, id=id)
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(resource, field, value)
    
    resource.save()
    return resource


@router.delete("resources/{id}/", response=OkSchema)
def delete_resource(request: Request, id: int):
    resource = get_object_or_404(Resource, id=id)
    resource.delete()
    return OkSchema(message=_("Resource deleted successfully."))



@router.get("resources/{id}/", response=DetailResourceOut, auth=ninja_jwt_auth_optional)
def detail_resource(request: Request, id: int):
    resource = get_object_or_404(Resource.objects.select_related("publisher"), id=id)
    
    # Only create usage event for authenticated users
    if hasattr(request, 'user') and request.user and request.user.is_authenticated:
        create_usage_event_task.delay({
            "developer_user_id": request.user.id,
            "usage_kind": UsageEvent.UsageKindChoice.VIEW,
            "subject_kind": UsageEvent.SubjectKindChoice.RESOURCE,
            "asset_id": None,
            "resource_id": resource.id,
            "metadata": {},
            "ip_address": getattr(request, 'client', {}).get('host') if hasattr(request, 'client') else request.META.get('REMOTE_ADDR'),
            "user_agent": request.headers.get('User-Agent', ''),
            "effective_license": ""  # Resources don't have license field
        })
    
    return resource
