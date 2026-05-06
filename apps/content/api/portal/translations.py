import logging
from typing import Annotated, Literal

from django.utils.translation import gettext_lazy as _
from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, AssetVersion, CategoryChoice, LicenseChoice, StatusChoice
from apps.content.services.translation import TranslationService
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

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])
logger = logging.getLogger(__name__)


# --- Output Schemas ---


class TranslationPublisherOut(Schema):
    id: int
    name: str


class TranslationListOut(Schema):
    id: int
    slug: str
    name: str
    description: str
    publisher: TranslationPublisherOut
    license: LicenseChoice
    language: str
    is_external: bool
    thumbnail_url: str | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None


class TranslationVersionOut(Schema):
    id: int
    name: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime


class TranslationDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    slug: str
    thumbnail_url: str | None = None
    publisher: TranslationPublisherOut
    license: LicenseChoice
    language: str
    is_external: bool
    external_url: str | None = None
    versions: list[TranslationVersionOut]
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_versions(obj: Asset) -> list[AssetVersion]:
        return list(obj.versions.all())


# --- Input Schemas ---


class TranslationCreateIn(Schema):
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


class TranslationPutIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    license: LicenseChoice
    language: str = Field(..., max_length=10)
    publisher_id: int
    is_external: bool = False
    external_url: str | None = None


class TranslationPatchIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    license: LicenseChoice | None = None
    language: str | None = None
    publisher_id: int | None = None
    is_external: bool | None = None
    external_url: str | None = None


# --- Filter Schema ---


class TranslationFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    language: Annotated[str | None, FilterLookup(q="language")] = None
    is_external: Annotated[bool | None, FilterLookup(q="is_external")] = None


# --- Endpoints ---


@router.get("translations/", response=list[TranslationListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TRANSLATION)])
@paginate
@ordering(ordering_fields=["id", "name", "created_at", "updated_at"])
@searching(search_fields=["name", "name_ar", "description", "description_ar", "publisher__name"])
def list_translations(request: Request, filters: TranslationFilter = Query()):
    qs = Asset.objects.select_related("publisher").filter(
        request.publisher_q(),
        category=CategoryChoice.TRANSLATION,
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
    "translations/",
    response={
        201: TranslationDetailOut,
        400: NinjaErrorResponse[Literal["translation_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["publisher_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_TRANSLATION)])
def create_translation(
    request: Request,
    data: TranslationCreateIn,
) -> tuple[int, Asset]:
    logger.info(
        f"Creating translation [publisher_id={data.publisher_id}, language={data.language}, user_id={request.user.id}]"
    )
    enforce_publisher_membership(request.user, data.publisher_id)
    service = TranslationService()
    translation = service.create_translation(
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
    )
    logger.info(f"Translation created [translation_id={translation.id}, user_id={request.user.id}]")
    return 201, translation


@router.get(
    "translations/{translation_slug}/",
    response={
        200: TranslationDetailOut,
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TRANSLATION)])
def retrieve_translation(request: Request, translation_slug: str) -> Asset:
    try:
        return (
            Asset.objects.select_related("publisher")
            .prefetch_related("versions")
            .filter(request.publisher_q())
            .get(
                slug=translation_slug,
                category=CategoryChoice.TRANSLATION,
                status=StatusChoice.READY,
            )
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc


@router.put(
    "translations/{translation_slug}/",
    response={
        200: TranslationDetailOut,
        400: NinjaErrorResponse[Literal["translation_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TRANSLATION)])
def update_translation_put(
    request: Request,
    translation_slug: str,
    data: TranslationPutIn,
) -> Asset:
    logger.info(f"Updating translation (PUT) [translation_slug={translation_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = TranslationService()
    fields = data.model_dump()
    translation = service.update_translation(translation_slug, fields=fields, user_publisher_q=request.publisher_q())
    logger.info(f"Translation updated [translation_id={translation.id}, user_id={request.user.id}]")
    return translation


@router.patch(
    "translations/{translation_slug}/",
    response={
        200: TranslationDetailOut,
        400: NinjaErrorResponse[Literal["translation_name_required"]]
        | NinjaErrorResponse[Literal["external_url_required"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TRANSLATION)])
def update_translation_patch(
    request: Request,
    translation_slug: str,
    data: TranslationPatchIn,
) -> Asset:
    logger.info(f"Updating translation (PATCH) [translation_slug={translation_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = TranslationService()
    fields = data.model_dump(exclude_unset=True)
    translation = service.update_translation(translation_slug, fields=fields, user_publisher_q=request.publisher_q())
    logger.info(f"Translation updated [translation_id={translation.id}, user_id={request.user.id}]")
    return translation


@router.delete(
    "translations/{translation_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_TRANSLATION)])
def delete_translation(request: Request, translation_slug: str) -> tuple[int, None]:
    logger.info(f"Deleting translation [translation_slug={translation_slug}, user_id={request.user.id}]")
    service = TranslationService()
    service.delete_translation(translation_slug, user_publisher_q=request.publisher_q())
    logger.info(f"Translation deleted [translation_slug={translation_slug}, user_id={request.user.id}]")
    return 204, None
