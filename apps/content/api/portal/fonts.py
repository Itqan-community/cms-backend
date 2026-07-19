import logging
from typing import Annotated, Literal

from django.utils.translation import gettext_lazy as _
from ninja import Field, File, FilterLookup, FilterSchema, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import Asset, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.services.font import FontService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.publishers.services.membership import enforce_publisher_membership

router = ItqanRouter(tags=[NinjaTag.FONTS])
logger = logging.getLogger(__name__)


# --- Output Schemas ---


class FontPublisherOut(Schema):
    id: int
    name: str


class FontListOut(Schema):
    id: int
    slug: str
    name: str
    description: str
    publisher: FontPublisherOut = Field(..., alias="publisher")
    license: LicenseChoice
    language: str
    is_external: bool
    is_open_access: bool
    restricted_for_tenant: bool
    thumbnail_url: str | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None


class FontVersionOut(Schema):
    id: int
    name: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_file_url(obj: AssetVersion) -> str | None:
        if obj.file_url:
            return obj.file_url.url
        return None


class FontDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    slug: str
    thumbnail_url: str | None = None
    publisher: FontPublisherOut = Field(..., alias="publisher")
    license: LicenseChoice
    language: str
    is_external: bool
    external_url: str | None = None
    is_open_access: bool
    restricted_for_tenant: bool
    versions: list[FontVersionOut]
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_versions(obj: Asset) -> list[FontVersionOut]:
        return list(obj.versions.all())


# --- Input Schemas ---


class FontCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    license: LicenseChoice
    language: str = Field(..., max_length=10)
    publisher_id: int
    is_external: bool = False
    external_url: str | None = None
    is_open_access: bool = False
    restricted_for_tenant: bool = False


class FontPutIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str = ""
    description_en: str = ""
    long_description_ar: str = ""
    long_description_en: str = ""
    license: LicenseChoice
    language: str = Field(..., max_length=10)
    publisher_id: int
    is_external: bool = False
    external_url: str | None = None
    is_open_access: bool = False
    restricted_for_tenant: bool = False


class FontPatchIn(Schema):
    name_ar: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    license: LicenseChoice | None = None
    language: str | None = Field(default=None, max_length=10)
    publisher_id: int | None = None
    is_external: bool | None = None
    external_url: str | None = None
    is_open_access: bool | None = None
    restricted_for_tenant: bool | None = None


# --- Filter Schema ---


class FontFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    language: Annotated[str | None, FilterLookup(q="language")] = None
    is_external: Annotated[bool | None, FilterLookup(q="is_external")] = None


# --- Endpoints ---


@router.get("fonts/", response=list[FontListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_FONT)])
@paginate
@ordering(ordering_fields=["id", "name", "created_at", "updated_at"])
@searching(
    search_fields=[
        "name",
        "name_ar",
        "name_en",
        "description",
        "description_ar",
        "description_en",
        "publisher__name",
    ]
)
def list_fonts(request: Request, filters: FontFilter = Query()):
    qs = Asset.objects.select_related("publisher").filter(
        request.publisher_q(),
        category=CategoryChoice.FONT,
        status=StatusChoice.READY,
    )

    filters_dict = filters.model_dump(exclude_none=True)
    if publisher_ids := filters_dict.get("publisher_id"):
        qs = qs.filter(publisher_id__in=publisher_ids)
    if license_codes := filters_dict.get("license_code"):
        qs = qs.filter(license__in=license_codes)
    if language := filters_dict.get("language"):
        qs = qs.filter(language=language)
    if "is_external" in filters_dict:
        qs = qs.filter(is_external=filters_dict["is_external"])

    return qs.distinct()


@router.post(
    "fonts/",
    response={
        201: FontDetailOut,
        400: NinjaErrorResponse[Literal["font_name_required"]] | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["publisher_not_found"]] | NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_FONT)])
def create_font(
    request: Request,
    data: Form[FontCreateIn],
    thumbnail: UploadedFile | None = File(None),
) -> tuple[int, Asset]:
    logger.info(
        f"Creating font [publisher_id={data.publisher_id}, language={data.language}, user_id={request.user.id}]"
    )
    enforce_publisher_membership(request.user, data.publisher_id)
    service = FontService()
    font = service.create_font(
        publisher_id=data.publisher_id,
        name_ar=data.name_ar,
        name_en=data.name_en,
        description_ar=data.description_ar,
        description_en=data.description_en,
        long_description_ar=data.long_description_ar,
        long_description_en=data.long_description_en,
        license=data.license,
        language=data.language,
        is_external=data.is_external,
        external_url=data.external_url,
        thumbnail_url=thumbnail,
        is_open_access=data.is_open_access,
        restricted_for_tenant=data.restricted_for_tenant,
    )
    logger.info(f"Font created [font_id={font.id}, user_id={request.user.id}]")
    return 201, font


@router.get(
    "fonts/{font_slug}/",
    response={
        200: FontDetailOut,
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_FONT)])
def retrieve_font(request: Request, font_slug: str) -> Asset:
    try:
        return (
            Asset.objects.select_related("publisher")
            .prefetch_related("versions")
            .filter(request.publisher_q())
            .get(slug=font_slug, category=CategoryChoice.FONT)
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="font_not_found",
            message=_("Font with slug {slug} not found.").format(slug=font_slug),
            status_code=404,
        ) from exc


@router.put(
    "fonts/{font_slug}/",
    response={
        200: FontDetailOut,
        400: NinjaErrorResponse[Literal["font_name_required"]] | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_FONT)])
def update_font_put(
    request: Request,
    font_slug: str,
    data: Form[FontPutIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating font (PUT) [font_slug={font_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = FontService()
    fields = data.model_dump()
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    font = service.update_font(font_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Font updated [font_id={font.id}, user_id={request.user.id}]")
    return font


@router.patch(
    "fonts/{font_slug}/",
    response={
        200: FontDetailOut,
        400: NinjaErrorResponse[Literal["font_name_required"]] | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_FONT)])
def update_font_patch(
    request: Request,
    font_slug: str,
    data: Form[FontPatchIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating font (PATCH) [font_slug={font_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = FontService()
    fields = data.model_dump(exclude_unset=True)
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    font = service.update_font(font_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Font updated [font_id={font.id}, user_id={request.user.id}]")
    return font


@router.delete(
    "fonts/{font_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_FONT)])
def delete_font(request: Request, font_slug: str) -> tuple[int, None]:
    logger.info(f"Deleting font [font_slug={font_slug}, user_id={request.user.id}]")
    service = FontService()
    service.delete_font(font_slug, publisher_q=request.publisher_q())
    logger.info(f"Font deleted [font_slug={font_slug}, user_id={request.user.id}]")
    return 204, None
