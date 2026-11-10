import logging
from typing import Annotated, Literal

from django.utils.translation import gettext_lazy as _
from ninja import Field, File, FilterLookup, FilterSchema, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.asset_tag_schemas import AssetTagOut
from apps.content.channel_schemas import ChannelConflictResponse
from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    LicenseChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.services.text_asset import TextAssetService
from apps.content.version_text import VersionText
from apps.core.mixins.storage import absolute_file_url
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

router = ItqanRouter(tags=[NinjaTag.TEXT_ASSETS])
logger = logging.getLogger(__name__)


# --- Output Schemas ---


class TextAssetPublisherOut(Schema):
    id: int
    name: str


class MushafLayoutBriefOut(Schema):
    id: int
    name: str
    page_count: int


class TextAssetListOut(Schema):
    id: int
    slug: str
    name: str
    description: str
    publisher: TextAssetPublisherOut = Field(..., alias="publisher")
    license: LicenseChoice
    language: str
    is_external: bool
    is_open_access: bool
    in_gallery: bool
    in_public_api: bool
    in_cli: bool
    in_tenants: bool
    status: StatusChoice
    thumbnail_url: str | None = None
    template: AssetTemplateChoice | None = None
    tags: list[AssetTagOut]
    mushaf_layout: MushafLayoutBriefOut | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None


class TextAssetVersionOut(Schema):
    id: int
    name: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_file_url(obj: AssetVersion, context: dict) -> str | None:
        return absolute_file_url(context["request"], obj.file_url)


class TextAssetDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    slug: str
    thumbnail_url: str | None = None
    publisher: TextAssetPublisherOut = Field(..., alias="publisher")
    license: LicenseChoice
    language: str
    is_external: bool
    external_url: str | None = None
    is_open_access: bool
    in_gallery: bool
    in_public_api: bool
    in_cli: bool
    in_tenants: bool
    status: StatusChoice
    template: AssetTemplateChoice | None = None
    tags: list[AssetTagOut]
    mushaf_layout: MushafLayoutBriefOut | None = None
    versions: list[TextAssetVersionOut]
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_versions(obj: Asset) -> list[TextAssetVersionOut]:
        return list(obj.versions.filter(state=VersionStateChoice.PUBLISHED))


# --- Input Schemas ---


class TextAssetCreateIn(Schema):
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
    in_gallery: bool = True
    in_public_api: bool = True
    in_cli: bool = True
    in_tenants: bool = True
    status: StatusChoice = StatusChoice.READY
    confirm_channel_change: bool = False
    version_label_en: str = Field(default="", max_length=255)
    version_label_ar: str = Field(default="", max_length=255)
    # Starting version number ("major.minor") — required when a file is uploaded.
    version_number: str | None = Field(default=None, max_length=20)
    version_summary_en: str = ""
    version_summary_ar: str = ""
    template: AssetTemplateChoice
    tags: list[str] = Field(default_factory=list, description="Tag slugs; the first one prefixes the package name.")
    mushaf_layout_id: int | None = None
    slug: str | None = Field(
        default=None,
        description="Package name from `POST /portal/ai/translate/` (`slug_for`); built from the names when omitted.",
    )


class TextAssetPutIn(Schema):
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
    in_gallery: bool = True
    in_public_api: bool = True
    in_cli: bool = True
    in_tenants: bool = True
    status: StatusChoice = StatusChoice.READY
    confirm_channel_change: bool = False
    tags: list[str] | None = Field(default=None, description="Tag slugs; omitted keeps the asset's tags.")


class TextAssetPatchIn(Schema):
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
    in_gallery: bool | None = None
    in_public_api: bool | None = None
    in_cli: bool | None = None
    in_tenants: bool | None = None
    status: StatusChoice | None = None
    confirm_channel_change: bool = False
    tags: list[str] | None = Field(default=None, description="Tag slugs; replaces the asset's tags when sent.")


# --- Filter Schema ---


class TextAssetFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    language: Annotated[str | None, FilterLookup(q="language")] = None
    is_external: Annotated[bool | None, FilterLookup(q="is_external")] = None
    template: AssetTemplateChoice | None = None
    tag: list[str] | None = None


# --- Endpoints ---


@router.get("text-assets/", response=list[TextAssetListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TEXT_ASSET)])
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
def list_text_assets(request: Request, filters: TextAssetFilter = Query()):
    qs = (
        Asset.objects.select_related("publisher", "mushaf_layout")
        .prefetch_related("tags")
        .filter(
            request.publisher_q(),
            category=CategoryChoice.TEXT,
        )
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
    if template := filters_dict.get("template"):
        qs = qs.filter(template=template)
    if tags := filters_dict.get("tag"):
        qs = qs.filter(tags__slug__in=tags)

    return qs.distinct()


@router.post(
    "text-assets/",
    response={
        201: TextAssetDetailOut,
        400: NinjaErrorResponse[Literal["text_asset_name_required"]]
        | NinjaErrorResponse[Literal["asset_slug_invalid"]]
        | NinjaErrorResponse[Literal["external_url_required"]]
        | NinjaErrorResponse[Literal["version_number_required"]]
        | NinjaErrorResponse[Literal["version_number_invalid"]]
        | NinjaErrorResponse[Literal["content_file_unparseable"]]
        | NinjaErrorResponse[Literal["content_file_missing_columns"]]
        | NinjaErrorResponse[Literal["content_file_invalid_rows"]]
        | NinjaErrorResponse[Literal["mushaf_layout_required"]]
        | NinjaErrorResponse[Literal["mushaf_layout_not_allowed"]]
        | NinjaErrorResponse[Literal["template_not_allowed"]]
        | NinjaErrorResponse[Literal["text_asset_tag_required"]]
        | NinjaErrorResponse[Literal["asset_tag_not_found"]],
        404: NinjaErrorResponse[Literal["publisher_not_found"]]
        | NinjaErrorResponse[Literal["text_asset_not_found"]]
        | NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_TEXT_ASSET)])
def create_text_asset(
    request: Request,
    data: Form[TextAssetCreateIn],
    thumbnail: UploadedFile | None = File(None),
    file: UploadedFile | None = File(None),
) -> tuple[int, Asset]:
    logger.info(
        f"Creating text asset [publisher_id={data.publisher_id}, language={data.language}, user_id={request.user.id}]"
    )
    enforce_publisher_membership(request.user, data.publisher_id)
    service = TextAssetService()
    text_asset = service.create_text_asset_with_optional_version(
        version_text=VersionText.from_data(data, prefix="version_"),
        version_number=data.version_number,
        file=file,
        created_by_id=request.user.id,
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
        in_gallery=data.in_gallery,
        in_public_api=data.in_public_api,
        in_cli=data.in_cli,
        in_tenants=data.in_tenants,
        status=data.status,
        slug=data.slug,
        template=data.template,
        tags=data.tags,
        mushaf_layout_id=data.mushaf_layout_id,
    )
    logger.info(f"Text asset created [text_asset_id={text_asset.id}, user_id={request.user.id}]")
    return 201, text_asset


@router.get(
    "text-assets/{text_asset_slug}/",
    response={
        200: TextAssetDetailOut,
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TEXT_ASSET)])
def retrieve_text_asset(request: Request, text_asset_slug: str) -> Asset:
    try:
        return (
            Asset.objects.select_related("publisher", "mushaf_layout")
            .prefetch_related("versions", "tags")
            .filter(request.publisher_q())
            .get(slug=text_asset_slug, category=CategoryChoice.TEXT)
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc


@router.put(
    "text-assets/{text_asset_slug}/",
    response={
        200: TextAssetDetailOut,
        400: NinjaErrorResponse[Literal["text_asset_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]]
        | NinjaErrorResponse[Literal["asset_template_immutable"]]
        | NinjaErrorResponse[Literal["template_not_allowed"]]
        | NinjaErrorResponse[Literal["text_asset_tag_required"]]
        | NinjaErrorResponse[Literal["asset_tag_not_found"]],
        409: ChannelConflictResponse,
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)])
def update_text_asset_put(
    request: Request,
    text_asset_slug: str,
    data: Form[TextAssetPutIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating text asset (PUT) [text_asset_slug={text_asset_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = TextAssetService()
    fields = data.model_dump()
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    text_asset = service.update_text_asset(text_asset_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Text asset updated [text_asset_id={text_asset.id}, user_id={request.user.id}]")
    return text_asset


@router.patch(
    "text-assets/{text_asset_slug}/",
    response={
        200: TextAssetDetailOut,
        400: NinjaErrorResponse[Literal["text_asset_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]]
        | NinjaErrorResponse[Literal["asset_template_immutable"]]
        | NinjaErrorResponse[Literal["template_not_allowed"]]
        | NinjaErrorResponse[Literal["text_asset_tag_required"]]
        | NinjaErrorResponse[Literal["asset_tag_not_found"]],
        409: ChannelConflictResponse,
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)])
def update_text_asset_patch(
    request: Request,
    text_asset_slug: str,
    data: Form[TextAssetPatchIn],
    thumbnail: UploadedFile | None = File(None),
) -> Asset:
    logger.info(f"Updating text asset (PATCH) [text_asset_slug={text_asset_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = TextAssetService()
    fields = data.model_dump(exclude_unset=True)
    if thumbnail is not None:
        fields["thumbnail_url"] = thumbnail
    text_asset = service.update_text_asset(text_asset_slug, fields=fields, publisher_q=request.publisher_q())
    logger.info(f"Text asset updated [text_asset_id={text_asset.id}, user_id={request.user.id}]")
    return text_asset


@router.delete(
    "text-assets/{text_asset_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_TEXT_ASSET)])
def delete_text_asset(request: Request, text_asset_slug: str) -> tuple[int, None]:
    logger.info(f"Deleting text asset [text_asset_slug={text_asset_slug}, user_id={request.user.id}]")
    service = TextAssetService()
    service.delete_text_asset(text_asset_slug, publisher_q=request.publisher_q())
    logger.info(f"Text asset deleted [text_asset_slug={text_asset_slug}, user_id={request.user.id}]")
    return 204, None
