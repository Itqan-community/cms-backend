from datetime import datetime

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, Reciter, Resource, UsageEvent
from apps.content.tasks import create_usage_event_task
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
    name: str = Field(min_length=1, description="Name cannot be empty")
    description: str
    category: Resource.CategoryChoice
    publisher_id: int


class UpdateResourceIn(Schema):
    name: str | None = Field(None, min_length=1, description="Name cannot be empty when provided")
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


class ContentReciterOut(Schema):
    id: int
    slug: str
    name: str
    name_ar: str
    recitations_count: int = Field(
        0,
        description="Number of READY recitation assets for this reciter",
    )


class RecitationFilter(FilterSchema):

    publisher_id: list[int] | None = Field(None, q="resource__publisher_id__in")
    reciter_id: list[int] | None = Field(None, q="reciter_id__in")
    riwayah_id: list[int] | None = Field(None, q="riwayah_id__in")


class ContentRecitationListOut(Schema):
    id: int
    resource_id: int
    name: str
    slug: str
    description: str
    reciter_id: int | None = None
    riwayah_id: int | None = None
    created_at: datetime
    updated_at: datetime


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
        publisher_id=data.publisher_id,
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


@router.get("resources/{id}/", response=DetailResourceOut, auth=None)
def detail_resource(request: Request, id: int):
    resource = get_object_or_404(Resource.objects.select_related("publisher"), id=id)

    # Only create usage event for authenticated users
    if hasattr(request, "user") and request.user and request.user.is_authenticated:
        create_usage_event_task.delay(
            {
                "developer_user_id": request.user.id,
                "usage_kind": UsageEvent.UsageKindChoice.VIEW,
                "subject_kind": UsageEvent.SubjectKindChoice.RESOURCE,
                "asset_id": None,
                "resource_id": resource.id,
                "metadata": {},
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": request.headers.get("User-Agent", ""),
                "effective_license": "",  # Resources don't have license field
            }
        )

    return resource


@router.get("reciters", response=list[ContentReciterOut], auth=None)
@paginate
@ordering(ordering_fields=["name", "name_ar", "slug"])
def list_content_reciters(request: Request):
    """
    Public Content API (V2):

    List reciters that have at least one READY recitation Asset.

    Conditions:
    - Reciter.is_active = True
    - Asset.category = RECITATION
    - Asset.reciter = this Reciter
    - Asset.resource.category = RECITATION
    - Asset.resource.status = READY
    """

    recitation_filter = Q(
        assets__category=Asset.CategoryChoice.RECITATION,
        assets__reciter__isnull=False,
        assets__resource__category=Resource.CategoryChoice.RECITATION,
        assets__resource__status=Resource.StatusChoice.READY,
    )

    qs = (
        Reciter.objects.filter(
            is_active=True,
        )
        .filter(recitation_filter)
        .distinct()
        .annotate(
            recitations_count=Count(
                "assets",
                filter=recitation_filter,
            )
        )
        .order_by("name")
    )

    return qs


@router.get(
    "recitations",
    response=list[ContentRecitationListOut],
    auth=None,
)
@paginate
@ordering(ordering_fields=["name", "created_at", "updated_at"])
@searching(search_fields=["name", "description", "resource__publisher__name", "reciter__name"])
def list_recitations(request, filters: RecitationFilter = Query()):

    qs = Asset.objects.select_related("resource", "reciter").filter(
        category=Asset.CategoryChoice.RECITATION,
        resource__category=Resource.CategoryChoice.RECITATION,
        resource__status=Resource.StatusChoice.READY,
    )

    qs = filters.filter(qs)

    return qs
