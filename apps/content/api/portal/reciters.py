import datetime
from typing import Annotated, Literal

from django.db import IntegrityError
from django.utils.translation import gettext as _
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import Field, field_validator

from apps.content.models import Nationality, Reciter
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

# TODO: to not block merging contributor PR, consider moving this api to api/portal/ since it's only used for admin dashboard.

router = ItqanRouter(tags=[NinjaTag.RECITERS])


class ReciterCreateIn(Schema):
    """Schema for creating a new reciter."""

    name: str = Field(..., max_length=255)
    name_ar: str = Field(..., max_length=255)
    name_en: str = Field(..., max_length=255)
    nationality_id: int | None = None
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

    @field_validator("bio")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Strip leading/trailing whitespace from bio field."""
        return v.strip()


class ReciterUpdateIn(Schema):
    """Schema for updating an existing reciter."""

    name: str | None = Field(None, max_length=255)
    name_ar: str | None = Field(None, max_length=255)
    name_en: str | None = Field(None, max_length=255)
    nationality_id: int | None = None
    date_of_birth: datetime.date | None = None
    date_of_death: datetime.date | None = None
    bio: str | None = None

    @field_validator("name", "name_ar", "name_en")
    @classmethod
    def name_must_not_be_blank(cls, v: str | None) -> str | None:
        """Validate that name fields are not blank or null if provided."""
        if v is None:
            raise ValueError("This field cannot be null.")
        v = v.strip()
        if not v:
            raise ValueError("Name must not be blank.")
        return v


class NationalityOut(Schema):
    """Schema for nationality nested in reciter output."""

    id: int
    name: str


class ReciterOut(Schema):
    """Schema for reciter output representation."""

    id: int
    name: str
    name_ar: str | None
    name_en: str | None
    slug: str
    nationality: NationalityOut | None
    date_of_birth: datetime.date | None
    date_of_death: datetime.date | None
    bio: str
    is_active: bool

    @staticmethod
    def resolve_bio(obj: Reciter) -> str:
        return obj.bio or ""

    @staticmethod
    def resolve_nationality(obj: Reciter) -> NationalityOut | None:
        if not obj.nationality:
            return None
        return NationalityOut(id=obj.nationality.id, name=obj.nationality.name)


class ReciterFilter(FilterSchema):
    """Filter schema for reciter list endpoint."""

    name: Annotated[list[str] | None, FilterLookup(q="name__in")] = None
    name_ar: Annotated[list[str] | None, FilterLookup(q="name_ar__in")] = None
    slug: Annotated[list[str] | None, FilterLookup(q="slug__in")] = None
    is_active: Annotated[bool | None, FilterLookup(q="is_active")] = None
    nationality: Annotated[str | None, FilterLookup(q="nationality__name__icontains")] = None


@router.post(
    "reciters/",
    response={
        201: ReciterOut,
        401: NinjaErrorResponse[Literal["unauthorized"], Literal[None]],
        404: NinjaErrorResponse[Literal["nationality_not_found"], Literal[None]],
        409: NinjaErrorResponse[Literal["reciter_already_exists"], Literal[None]]
        | NinjaErrorResponse[Literal["reciter_conflict"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def create_reciter(request: Request, data: ReciterCreateIn) -> tuple[int, Reciter]:
    """Create a new reciter with the given data."""
    if Reciter.objects.filter(name=data.name).exists():
        raise ItqanError(
            error_name="reciter_already_exists",
            message=_("A reciter with the name '{name}' already exists.").format(name=data.name),
            status_code=409,
        )

    nationality_obj: Nationality | None = None
    if data.nationality_id is not None:
        try:
            nationality_obj = Nationality.objects.get(id=data.nationality_id)
        except Nationality.DoesNotExist:
            raise ItqanError(
                error_name="nationality_not_found",
                message=_("Nationality with id {id} not found.").format(id=data.nationality_id),
                status_code=404,
            ) from None

    try:
        reciter = Reciter.objects.create(
            name=data.name,
            name_ar=data.name_ar,
            name_en=data.name_en,
            nationality=nationality_obj,
            date_of_birth=data.date_of_birth,
            date_of_death=data.date_of_death,
            bio=data.bio,
        )
    except IntegrityError:
        raise ItqanError(
            error_name="reciter_conflict",
            message=_("A reciter with conflicting unique fields already exists."),
            status_code=409,
        ) from None
    return 201, reciter


@router.get("reciters/", response=list[ReciterOut])
@paginate
@ordering(ordering_fields=["name", "nationality"])
@searching(search_fields=["name", "name_ar", "name_en", "slug", "nationality"])
def list_reciters(request: Request, filters: ReciterFilter = Query()) -> list[Reciter]:
    """List all reciters with optional filtering, ordering, and search."""
    qs = Reciter.objects.select_related("nationality").order_by("name")
    qs = filters.filter(qs)
    return qs


@router.get(
    "reciters/{reciter_id}/",
    response={
        200: ReciterOut,
        404: NinjaErrorResponse[Literal["reciter_not_found"], Literal[None]],
    },
)
def get_reciter(request: Request, reciter_id: int) -> Reciter:
    """Retrieve a single reciter by ID."""
    try:
        return Reciter.objects.select_related("nationality").get(id=reciter_id)
    except Reciter.DoesNotExist:
        raise ItqanError(
            error_name="reciter_not_found",
            message=_("Reciter with id {id} not found.").format(id=reciter_id),
            status_code=404,
        ) from None


@router.patch(
    "reciters/{reciter_id}/",
    response={
        200: ReciterOut,
        401: NinjaErrorResponse[Literal["unauthorized"], Literal[None]],
        404: NinjaErrorResponse[Literal["reciter_not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["nationality_not_found"], Literal[None]],
        409: NinjaErrorResponse[Literal["reciter_conflict"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def update_reciter(request: Request, reciter_id: int, data: ReciterUpdateIn) -> Reciter:
    """Update an existing reciter's fields."""
    try:
        reciter = Reciter.objects.select_related("nationality").get(id=reciter_id)
    except Reciter.DoesNotExist:
        raise ItqanError(
            error_name="reciter_not_found",
            message=_("Reciter with id {id} not found.").format(id=reciter_id),
            status_code=404,
        ) from None

    update_data = data.model_dump(exclude_unset=True)
    if "nationality_id" in update_data:
        nationality_id = update_data.pop("nationality_id")
        if nationality_id is not None:
            try:
                reciter.nationality = Nationality.objects.get(id=nationality_id)
            except Nationality.DoesNotExist:
                raise ItqanError(
                    error_name="nationality_not_found",
                    message=_("Nationality with id {id} not found.").format(id=nationality_id),
                    status_code=404,
                ) from None
        else:
            reciter.nationality = None
    for field, value in update_data.items():
        setattr(reciter, field, value)

    try:
        reciter.save()
    except IntegrityError:
        raise ItqanError(
            error_name="reciter_conflict",
            message=_("A reciter with conflicting unique fields already exists."),
            status_code=409,
        ) from None
    return reciter
