import datetime
import logging
from typing import Annotated, Literal

from ninja import Field, File, FilterLookup, FilterSchema, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import Reciter
from apps.content.services.reciter import ReciterService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.RECITERS])
logger = logging.getLogger(__name__)


class ReciterListOut(Schema):
    id: int
    name: str = Field(..., description="Fallback to name_en or name_ar if empty")
    bio: str
    recitations_count: int = Field(0, description="Number of READY recitation assets for this reciter")
    nationality: str | None = Field(None, description="2-letter ISO country code")
    slug: str
    image_url: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    date_of_death: datetime.date | None = None

    @staticmethod
    def resolve_nationality(obj: Reciter) -> str | None:
        if obj.nationality and hasattr(obj.nationality, "code"):
            return obj.nationality.code
        return obj.nationality if isinstance(obj.nationality, str) else None

    @staticmethod
    def resolve_image_url(obj: Reciter) -> str | None:
        return obj.image_url.url if obj.image_url else None


class ReciterDetailOut(Schema):
    id: int
    name_ar: str | None
    name_en: str | None
    bio_ar: str | None
    bio_en: str | None
    recitations_count: int = Field(0)
    nationality: str | None
    slug: str
    image_url: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    date_of_death: datetime.date | None = None

    @staticmethod
    def resolve_nationality(obj: Reciter) -> str | None:
        if obj.nationality and hasattr(obj.nationality, "code"):
            return obj.nationality.code
        return obj.nationality if isinstance(obj.nationality, str) else None

    @staticmethod
    def resolve_name_ar(obj: Reciter) -> str:
        return obj.name_ar or ""

    @staticmethod
    def resolve_name_en(obj: Reciter) -> str:
        return obj.name_en or ""

    @staticmethod
    def resolve_bio_ar(obj: Reciter) -> str:
        return obj.bio_ar or ""

    @staticmethod
    def resolve_bio_en(obj: Reciter) -> str:
        return obj.bio_en or ""

    @staticmethod
    def resolve_image_url(obj: Reciter) -> str | None:
        return obj.image_url.url if obj.image_url else None


class ReciterCreateIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    bio_ar: str = ""
    bio_en: str = ""
    nationality: str = Field("", pattern=r"^$|^[A-Za-z]{2}$", description="2-letter ISO country code")
    date_of_death: datetime.date | None = None


class ReciterPatchIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    bio_ar: str | None = None
    bio_en: str | None = None
    nationality: str | None = Field(None, pattern=r"^$|^[A-Za-z]{2}$", description="2-letter ISO country code")
    date_of_death: datetime.date | None = None


class ReciterFilter(FilterSchema):
    name_en: Annotated[str | None, FilterLookup(q="name_en__icontains")] = None
    name_ar: Annotated[str | None, FilterLookup(q="name_ar__icontains")] = None
    bio_en: Annotated[str | None, FilterLookup(q="bio_en__icontains")] = None
    bio_ar: Annotated[str | None, FilterLookup(q="bio_ar__icontains")] = None


@router.get("reciters/", response=list[ReciterListOut])
@permission_required([permission_class(PermissionChoice.READ_PORTAL_RECITER)])
@paginate
@ordering(
    ordering_fields=[
        "name",
        "recitations_count",
        "created_at",
        "updated_at",
    ]
)
@searching(search_fields=["name_en", "name_ar", "bio_en", "bio_ar"])
def list_reciters(request: Request, filters: ReciterFilter = Query()):
    service = ReciterService()
    qs = service.get_all_reciters()
    return filters.filter(qs)


@router.get(
    "reciters/{reciter_slug}/",
    response={
        200: ReciterDetailOut,
        404: NinjaErrorResponse[Literal["reciter_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.READ_PORTAL_RECITER)])
def get_reciter(request: Request, reciter_slug: str):
    service = ReciterService()
    return service.get_reciter(reciter_slug)


@router.post(
    "reciters/",
    response={
        201: ReciterListOut,
        400: NinjaErrorResponse[Literal["reciter_name_required"]],
        409: NinjaErrorResponse[Literal["reciter_already_exists"]],
    },
)
@permission_required([permission_class(PermissionChoice.CREATE_PORTAL_RECITER)])
def create_reciter(
    request: Request,
    data: Form[ReciterCreateIn],
    image: UploadedFile | None = File(None),
):
    logger.info(f"Creating reciter [user_id={request.user.id}]")
    service = ReciterService()
    reciter = service.create_reciter(
        name_ar=data.name_ar,
        name_en=data.name_en,
        bio_ar=data.bio_ar,
        bio_en=data.bio_en,
        nationality=data.nationality,
        date_of_death=data.date_of_death,
        image_url=image,
    )
    logger.info(f"Reciter created [reciter_id={reciter.id}, user_id={request.user.id}]")
    # The new reciter object won't have `recitations_count` annotated natively from create()
    # So we should fetch it from the service repo query
    return 201, service.get_reciter(reciter.slug)


@router.patch(
    "reciters/{reciter_slug}/",
    response={
        200: ReciterDetailOut,
        400: NinjaErrorResponse[Literal["reciter_name_required"]],
        404: NinjaErrorResponse[Literal["reciter_not_found"]],
        409: NinjaErrorResponse[Literal["reciter_already_exists"]],
    },
)
@permission_required([permission_class(PermissionChoice.UPDATE_PORTAL_RECITER)])
def patch_reciter(
    request: Request,
    reciter_slug: str,
    data: ReciterPatchIn,
):
    logger.info(f"Updating reciter [reciter_slug={reciter_slug}, user_id={request.user.id}]")
    service = ReciterService()

    fields = data.model_dump(exclude_unset=True)

    reciter = service.update_reciter(reciter_slug, fields)
    logger.info(f"Reciter updated [reciter_id={reciter.id}, user_id={request.user.id}]")
    return service.get_reciter(reciter.slug)


@router.delete(
    "reciters/{reciter_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["reciter_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.DELETE_PORTAL_RECITER)])
def delete_reciter(request: Request, reciter_slug: str):
    logger.info(f"Deleting reciter [reciter_slug={reciter_slug}, user_id={request.user.id}]")
    service = ReciterService()
    service.delete_reciter(reciter_slug)
    logger.info(f"Reciter deleted [reciter_slug={reciter_slug}, user_id={request.user.id}]")
    return 204, None
