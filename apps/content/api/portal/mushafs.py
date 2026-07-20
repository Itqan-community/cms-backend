import logging
from typing import Annotated, Literal

from django.utils.translation import gettext_lazy as _
from ninja import Field, File, FilterLookup, FilterSchema, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import Asset, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.services.mushaf import MushafService
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

router = ItqanRouter(tags=[NinjaTag.MUSHAFS])
logger = logging.getLogger(__name__)


# --- Output Schemas ---


class MushafPublisherOut(Schema):
    id: int
    name: str


class MushafListOut(Schema):
    id: int
    slug: str
    name: str
    description: str
    publisher: MushafPublisherOut = Field(..., alias="publisher")
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


class MushafVersionOut(Schema):
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


class MushafDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    slug: str
    thumbnail_url: str | None = None
    publisher: MushafPublisherOut = Field(..., alias="publisher")
    license: LicenseChoice
    language: str
    is_external: bool
    external_url: str | None = None
    is_open_access: bool
    restricted_for_tenant: bool
    versions: list[MushafVersionOut]
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_versions(obj: Asset) -> list[MushafVersionOut]:
        return list(obj.versions.all())


# --- Input Schemas ---


class MushafCreateIn(Schema):
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
    version_name: str | None = Field(default=None, max_length=255)
    version_summary: str = ""


class MushafPutIn(Schema):
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


class MushafPatchIn(Schema):
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


class MushafFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    language: Annotated[str | None, FilterLookup(q="language")] = None
    is_external: Annotated[bool | None, FilterLookup(q="is_external")] = None


# --- Endpoints ---


@router.get("mushafs/", response=list[MushafListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF)])
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
def list_mushafs(request: Request, filters: MushafFilter = Query()):
    qs = Asset.objects.select_related("publisher").filter(
        request.publisher_q(),
        category=CategoryChoice.MUSHAF,
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
    "mushafs/",
    response={
        201: MushafDetailOut,
        400: NinjaErrorResponse[Literal["mushaf_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]]
        | NinjaErrorResponse[Literal["version_name_required"]],
        404: NinjaErrorResponse[Literal["publisher_not_found"]] | NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_MUSHAF)])
def create_mushaf(
    request: Request,
    data: Form[MushafCreateIn],
    thumbnail: UploadedFile | None = File(None),
    file: UploadedFile | None = File(None),
) -> tuple[int, Asset]:
    logger.info(
        f"Creating mushaf [publisher_id={data.publisher_id}, language={data.language}, user_id={request.user.id}]"
    )
    enforce_publisher_membership(request.user, data.publisher_id)
    service = MushafService()
    mushaf = service.create_mushaf_with_optional_version(
        version_name=data.version_name,
        version_summary=data.version_summary,
        file=file,
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
    logger.info(f"Mushaf created [mushaf_id={mushaf.id}, user_id={request.user.id}]")
    return 201, mushaf


@router.get(
    "mushafs/{mushaf_slug}/",
    response={
        200: MushafDetailOut,
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF)])
def retrieve_mushaf(request: Request, mushaf_slug: str) -> Asset:
    try:
        return (
            Asset.objects.select_related("publisher")
            .prefetch_related("versions")
            .filter(request.publisher_q())
            .get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_not_found",
            message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
            status_code=404,
        ) from exc


@router.put(
    "mushafs/{mushaf_slug}/",
    response={
        200: MushafDetailOut,
        400: NinjaErrorResponse[Literal["mushaf_name_required"]] | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF)])
def update_mushaf_put(
    request: Request,
    mushaf_slug: str,
    data: Form[MushafPutIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating mushaf (PUT) [mushaf_slug={mushaf_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = MushafService()
    fields = data.model_dump()
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    mushaf = service.update_mushaf(mushaf_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Mushaf updated [mushaf_id={mushaf.id}, user_id={request.user.id}]")
    return mushaf


@router.patch(
    "mushafs/{mushaf_slug}/",
    response={
        200: MushafDetailOut,
        400: NinjaErrorResponse[Literal["mushaf_name_required"]] | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF)])
def update_mushaf_patch(
    request: Request,
    mushaf_slug: str,
    data: Form[MushafPatchIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating mushaf (PATCH) [mushaf_slug={mushaf_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = MushafService()
    fields = data.model_dump(exclude_unset=True)
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    mushaf = service.update_mushaf(mushaf_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Mushaf updated [mushaf_id={mushaf.id}, user_id={request.user.id}]")
    return mushaf


@router.delete(
    "mushafs/{mushaf_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_MUSHAF)])
def delete_mushaf(request: Request, mushaf_slug: str) -> tuple[int, None]:
    logger.info(f"Deleting mushaf [mushaf_slug={mushaf_slug}, user_id={request.user.id}]")
    service = MushafService()
    service.delete_mushaf(mushaf_slug, publisher_q=request.publisher_q())
    logger.info(f"Mushaf deleted [mushaf_slug={mushaf_slug}, user_id={request.user.id}]")
    return 204, None
