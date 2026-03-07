import datetime

from django.db import IntegrityError
from ninja import FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field, field_validator

from apps.content.models import Reciter
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterCreateIn(Schema):
    """Schema for creating a new reciter."""

    name: str
    name_ar: str
    name_en: str
    nationality: str = ""
    date_of_birth: datetime.date | None = None
    date_of_death: datetime.date | None = None
    bio: str = ""

    @field_validator("name", "name_ar", "name_en")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        """Validate that name fields are not blank after stripping whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank.")
        return v

    @field_validator("nationality", "bio")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from string fields."""
        return v.strip()


class ReciterUpdateIn(Schema):
    """Schema for updating an existing reciter."""

    name: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    nationality: str | None = None
    date_of_birth: datetime.date | None = None
    date_of_death: datetime.date | None = None
    bio: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        """Validate that name is not blank if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name must not be blank if provided.")
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

    @field_validator("nationality", "bio")
    @classmethod
    def non_nullable_string_must_not_be_null(cls, v: str | None) -> str | None:
        """Validate non-nullable string fields are not set to null."""
        if v is None:
            raise ValueError("This field cannot be null.")
        return v.strip()


class ReciterOut(Schema):
    """Schema for reciter output representation."""

    id: int
    name: str
    name_ar: str | None
    name_en: str | None
    slug: str
    nationality: str
    date_of_birth: datetime.date | None
    date_of_death: datetime.date | None
    bio: str
    is_active: bool


class ReciterFilter(FilterSchema):
    """Filter schema for reciter list endpoint."""

    name: list[str] | None = Field(None, q="name__in")
    name_ar: list[str] | None = Field(None, q="name_ar__in")
    slug: list[str] | None = Field(None, q="slug__in")
    is_active: bool | None = Field(None, q="is_active")
    nationality: str | None = Field(None, q="nationality__icontains")


@router.post(
    "reciters/",
    response={
        201: ReciterOut,
        409: NinjaErrorResponse,
    },
    auth=ninja_jwt_auth,
)
def create_reciter(request: Request, data: ReciterCreateIn) -> tuple[int, Reciter]:
    """Create a new reciter with the given data."""
    if Reciter.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="RECITER_ALREADY_EXISTS",
            message=f"A reciter with the name '{data.name}' already exists.",
            status_code=409,
        )

    try:
        reciter = Reciter.objects.create(
            name=data.name,
            name_ar=data.name_ar,
            name_en=data.name_en,
            nationality=data.nationality,
            date_of_birth=data.date_of_birth,
            date_of_death=data.date_of_death,
            bio=data.bio,
        )
    except IntegrityError:
        raise ItqanError(
            error_name="RECITER_CONFLICT",
            message="A reciter with conflicting unique fields already exists.",
            status_code=409,
        ) from None
    return 201, reciter


@router.get("reciters/", response=list[ReciterOut])
@paginate
@ordering(ordering_fields=["name", "nationality"])
@searching(search_fields=["name", "name_ar", "name_en", "slug", "nationality"])
def list_reciters(request: Request, filters: ReciterFilter = Query()) -> list[Reciter]:
    """List all reciters with optional filtering, ordering, and search."""
    qs = Reciter.objects.all().order_by("name")
    qs = filters.filter(qs)
    return qs


@router.get(
    "reciters/{reciter_id}/",
    response={
        200: ReciterOut,
        404: NinjaErrorResponse,
    },
)
def get_reciter(request: Request, reciter_id: int) -> Reciter:
    """Retrieve a single reciter by ID."""
    try:
        return Reciter.objects.get(id=reciter_id)
    except Reciter.DoesNotExist:
        raise ItqanError(
            error_name="RECITER_NOT_FOUND",
            message=f"Reciter with id {reciter_id} not found.",
            status_code=404,
        ) from None


@router.patch(
    "reciters/{reciter_id}/",
    response={
        200: ReciterOut,
        404: NinjaErrorResponse,
        409: NinjaErrorResponse,
    },
    auth=ninja_jwt_auth,
)
def update_reciter(request: Request, reciter_id: int, data: ReciterUpdateIn) -> Reciter:
    """Update an existing reciter's fields."""
    try:
        reciter = Reciter.objects.get(id=reciter_id)
    except Reciter.DoesNotExist:
        raise ItqanError(
            error_name="RECITER_NOT_FOUND",
            message=f"Reciter with id {reciter_id} not found.",
            status_code=404,
        ) from None

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reciter, field, value)

    try:
        reciter.save()
    except IntegrityError:
        raise ItqanError(
            error_name="RECITER_CONFLICT",
            message="A reciter with conflicting unique fields already exists.",
            status_code=409,
        ) from None
    return reciter
