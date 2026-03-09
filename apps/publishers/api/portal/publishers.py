from django.db import IntegrityError
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field, field_validator

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
    """Schema for creating a new publisher."""

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

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        """Validate that name is not blank after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank.")
        return v

    @field_validator("name_ar", "name_en")
    @classmethod
    def optional_name_must_not_be_blank(cls, v: str | None) -> str | None:
        """Validate that optional name fields are not blank if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name must not be blank if provided.")
        return v


class PublisherPutIn(Schema):
    """Schema for fully replacing a publisher (PUT)."""

    name: str
    name_ar: str | None = None
    name_en: str | None = None
    description: str
    description_ar: str | None = None
    description_en: str | None = None
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None = None
    country: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        """Validate that name is not blank after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank.")
        return v

    @field_validator("name_ar", "name_en")
    @classmethod
    def optional_name_must_not_be_blank(cls, v: str | None) -> str | None:
        """Validate that optional name fields are not blank if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name must not be blank if provided.")
        return v


class PublisherUpdateIn(Schema):
    """Schema for partially updating a publisher."""

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

    @field_validator("name", "name_ar", "name_en")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        """Validate that name fields are not blank if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name must not be blank if provided.")
        return v


class PublisherOut(Schema):
    """Schema for publisher output representation."""

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
    """Filter schema for publisher list endpoint."""

    is_verified: bool | None = Field(None, q="is_verified")
    country: str | None = Field(None, q="country__icontains")


@router.post(
    "publishers/",
    response={201: PublisherOut, 401: NinjaErrorResponse, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def create_publisher(request: Request, data: PublisherCreateIn) -> tuple[int, Publisher]:
    """Create a new publisher with the given data."""
    if Publisher.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="PUBLISHER_ALREADY_EXISTS",
            message=f"A publisher with the name '{data.name}' already exists.",
            status_code=409,
        )

    try:
        publisher = Publisher.objects.create(**data.dict())
    except IntegrityError:
        raise ItqanError(
            error_name="PUBLISHER_ALREADY_EXISTS",
            message=f"A publisher with the name '{data.name}' already exists.",
            status_code=409,
        ) from None
    return 201, publisher


@router.get("publishers/", response=list[PublisherOut])
@paginate
@ordering(ordering_fields=["name", "created_at"])
@searching(
    search_fields=[
        "name",
        "name_ar",
        "name_en",
        "description",
        "description_ar",
        "description_en",
    ]
)
def list_publishers(request: Request, filters: PublisherFilter = Query()) -> list[Publisher]:
    """List all publishers with optional filtering, ordering, and search."""
    qs = Publisher.objects.all().order_by("name")
    qs = filters.filter(qs)
    return qs


@router.get(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 404: NinjaErrorResponse},
)
def get_publisher(request: Request, publisher_id: int) -> Publisher:
    """Retrieve a single publisher by ID."""
    try:
        return Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="PUBLISHER_NOT_FOUND",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        ) from None


@router.put(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 401: NinjaErrorResponse, 404: NinjaErrorResponse, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def update_publisher_full(request: Request, publisher_id: int, data: PublisherPutIn) -> Publisher:
    """Fully update a publisher with the given data."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="PUBLISHER_NOT_FOUND",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        ) from None

    for field, value in data.dict().items():
        setattr(publisher, field, value)

    try:
        publisher.save()
    except IntegrityError:
        raise ItqanError(
            error_name="PUBLISHER_CONFLICT",
            message="A publisher with conflicting unique fields already exists.",
            status_code=409,
        ) from None
    return publisher


@router.patch(
    "publishers/{publisher_id}/",
    response={200: PublisherOut, 401: NinjaErrorResponse, 404: NinjaErrorResponse, 409: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def update_publisher_partial(request: Request, publisher_id: int, data: PublisherUpdateIn) -> Publisher:
    """Partially update a publisher's fields."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="PUBLISHER_NOT_FOUND",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        ) from None

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(publisher, field, value)

    try:
        publisher.save()
    except IntegrityError:
        raise ItqanError(
            error_name="PUBLISHER_CONFLICT",
            message="A publisher with conflicting unique fields already exists.",
            status_code=409,
        ) from None
    return publisher


@router.delete(
    "publishers/{publisher_id}/",
    response={204: None, 401: NinjaErrorResponse, 404: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def delete_publisher(request: Request, publisher_id: int) -> tuple[int, None]:
    """Delete a publisher by ID."""
    try:
        publisher = Publisher.objects.get(id=publisher_id)
    except Publisher.DoesNotExist:
        raise ItqanError(
            error_name="PUBLISHER_NOT_FOUND",
            message=f"Publisher with id {publisher_id} not found.",
            status_code=404,
        ) from None

    publisher.delete()
    return 204, None
