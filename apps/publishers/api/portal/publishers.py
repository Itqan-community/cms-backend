from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherCreateIn(Schema):
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    description: str = ""
    description_ar: str | None = None
    description_en: str | None = None
    address: str = ""
    website: str = ""
    contact_email: str = ""
    is_verified: bool = True
    foundation_year: int | None = None
    country: str = ""


class PublisherUpdateIn(Schema):
    name: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    description: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    address: str | None = None
    website: str | None = None
    contact_email: str | None = None
    is_verified: bool | None = None
    foundation_year: int | None = None
    country: str | None = None


class PublisherOut(Schema):
    id: int
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    slug: str
    description: str
    description_ar: str | None = None
    description_en: str | None = None
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None = None
    country: str
    icon_url: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PublisherFilter(FilterSchema):
    is_verified: bool | None = Field(None, q="is_verified")
    country: str | None = Field(None, q="country__icontains")


@router.post(
    "publishers/",
    response={201: PublisherOut, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def create_publisher(request: Request, data: PublisherCreateIn):
    if Publisher.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="publisher_already_exists",
            message=f"A publisher with the name '{data.name}' already exists.",
            status_code=409,
        )

    publisher = Publisher.objects.create(**data.dict())
    return 201, publisher


@router.get("publishers/", response=list[PublisherOut])
@paginate
@ordering(ordering_fields=["name", "created_at"])
@searching(search_fields=["name", "name_ar", "description", "description_ar"])
def list_publishers(request: Request, filters: PublisherFilter = Query()):
    qs = Publisher.objects.all().order_by("name")
    qs = filters.filter(qs)
    return qs


@router.get(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 404: NinjaErrorResponse},
)
def get_publisher(request: Request, publisher_id: int):
    try:
        return Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="publisher_not_found",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        )


@router.put(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 404: NinjaErrorResponse, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def update_publisher_full(request: Request, publisher_id: int, data: PublisherCreateIn):
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="publisher_not_found",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        )

    if data.name != publisher.name and Publisher.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="publisher_already_exists",
            message=f"A publisher with the name '{data.name}' already exists.",
            status_code=409,
        )

    for field, value in data.dict().items():
        setattr(publisher, field, value)
    publisher.save()
    return publisher


@router.patch(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 404: NinjaErrorResponse, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def update_publisher_partial(request: Request, publisher_id: int, data: PublisherUpdateIn):
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="publisher_not_found",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        )

    update_data = data.dict(exclude_unset=True)

    if "name" in update_data and update_data["name"] != publisher.name:
        if Publisher.objects.filter(name=update_data["name"]).exists():
            raise ItqanError(
                error_name="publisher_already_exists",
                message=f"A publisher with the name '{update_data['name']}' already exists.",
                status_code=409,
            )

    for field, value in update_data.items():
        setattr(publisher, field, value)
    publisher.save()
    return publisher


@router.delete(
    "publishers/{publisher_id}/",
    response={204: None, 404: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def delete_publisher(request: Request, publisher_id: int):
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="publisher_not_found",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        )

    publisher.delete()
    return 204, None
