import logging
from typing import Annotated, Literal

from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _
from ninja import Field, FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import Asset, CategoryChoice, LicenseChoice, Riwayah, StatusChoice
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.publishers.services.membership import enforce_publisher_membership

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])
logger = logging.getLogger(__name__)


# --- Output Schemas ---


class MinimalReciter(Schema):
    id: int
    name: str


class MinimalQiraah(Schema):
    id: int
    name: str
    bio: str


class MinimalRiwayah(Schema):
    id: int
    name: str
    bio: str


class PublisherRef(Schema):
    id: int
    name: str


class RecitationListOut(Schema):
    id: int
    slug: str
    name: str
    description: str
    publisher: PublisherRef
    reciter: MinimalReciter | None = None
    qiraah: MinimalQiraah | None = None
    riwayah: MinimalRiwayah | None = None
    madd_level: str | None = None
    meem_behaviour: str | None = None
    year: int | None = None
    license: LicenseChoice
    thumbnail_url: str | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None


class RecitationDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    slug: str
    thumbnail_url: str | None = None
    publisher: PublisherRef
    reciter: MinimalReciter | None = None
    qiraah: MinimalQiraah | None = None
    riwayah: MinimalRiwayah | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice
    created_at: AwareDatetime
    updated_at: AwareDatetime
    ayah_timings_url: AbsoluteUrl | None = None

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_ayah_timings_url(obj: Asset) -> str | None:
        if version := obj.versions.first():
            return version.file_url.url if version.file_url else None
        return None


# --- Input Schemas ---


class RecitationCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str = ""
    description_en: str = ""
    publisher_id: int
    reciter_id: int
    qiraah_id: int | None = None
    riwayah_id: int | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice


class RecitationPutIn(Schema):
    name_ar: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    description_ar: str | None = None
    description_en: str | None = None
    publisher_id: int
    reciter_id: int
    qiraah_id: int | None = None
    riwayah_id: int | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice


class RecitationPatchIn(Schema):
    name_ar: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    description_ar: str | None = None
    description_en: str | None = None
    publisher_id: int | None = None
    reciter_id: int | None = None
    qiraah_id: int | None = None
    riwayah_id: int | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice | None = None


# --- Filter Schema ---


class RecitationFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="publisher_id__in")] = None
    reciter_id: Annotated[list[int] | None, FilterLookup(q="reciter_id__in")] = None
    qiraah_id: Annotated[list[int] | None, FilterLookup(q="qiraah_id__in")] = None
    riwayah_id: Annotated[list[int] | None, FilterLookup(q="riwayah_id__in")] = None
    madd_level: Annotated[list[Asset.MaddLevelChoice] | None, FilterLookup(q="madd_level__in")] = None
    meem_behaviour: Annotated[list[Asset.MeemBehaviourChoice] | None, FilterLookup(q="meem_behaviour__in")] = None
    year: Annotated[int | None, FilterLookup(q="year")] = None
    license_code: Annotated[list[LicenseChoice] | None, FilterLookup(q="license__in")] = None


# --- Endpoints ---


@router.get("recitations/", response=list[RecitationListOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
@paginate
@ordering(
    ordering_fields=[
        "id",
        "name",
        "reciter_name",
        "qiraah_name",
        "riwayah_name",
        "madd_level",
        "meem_behaviour",
        "year",
        "license",
        "created_at",
        "updated_at",
    ]
)
@searching(
    search_fields=[
        "name",
        "name_ar",
        "name_en",
        "description",
        "description_ar",
        "description_en",
        "publisher__name",
        "reciter__name",
    ]
)
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    qs = Asset.objects.select_related("publisher", "reciter", "riwayah", "qiraah").filter(
        request.user_publisher_q(),
        category=CategoryChoice.RECITATION,
        status=StatusChoice.READY,
    )

    filters_dict = filters.model_dump(exclude_none=True)
    if reciter_ids := filters_dict.get("reciter_id"):
        qs = qs.filter(reciter_id__in=reciter_ids)
    if riwayah_ids := filters_dict.get("riwayah_id"):
        qs = qs.filter(
            Q(riwayah_id__in=riwayah_ids)
            | Q(riwayah__isnull=True, qiraah__in=Riwayah.objects.filter(id__in=riwayah_ids).values("qiraah_id"))
        )
    if qiraah_ids := filters_dict.get("qiraah_id"):
        qs = qs.filter(qiraah_id__in=qiraah_ids)
    if publisher_ids := filters_dict.get("publisher_id"):
        qs = qs.filter(publisher_id__in=publisher_ids)
    if madd_levels := filters_dict.get("madd_level"):
        qs = qs.filter(madd_level__in=madd_levels)
    if meem_behaviours := filters_dict.get("meem_behaviour"):
        qs = qs.filter(meem_behaviour__in=meem_behaviours)
    if year := filters_dict.get("year"):
        qs = qs.filter(year=year)
    if license_codes := filters_dict.get("license_code"):
        qs = qs.filter(license__in=license_codes)

    qs = qs.annotate(
        reciter_name=F("reciter__name"),
        qiraah_name=F("qiraah__name"),
        riwayah_name=F("riwayah__name"),
    )
    return qs.distinct()


@router.post(
    "recitations/",
    response={
        201: RecitationDetailOut,
        400: NinjaErrorResponse[Literal["recitation_name_required"]]
        | NinjaErrorResponse[Literal["invalid_riwayah_qiraah_combo"]],
        404: NinjaErrorResponse[Literal["publisher_not_found"]]
        | NinjaErrorResponse[Literal["reciter_not_found"]]
        | NinjaErrorResponse[Literal["qiraah_not_found"]]
        | NinjaErrorResponse[Literal["riwayah_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)])
def create_recitation(
    request: Request,
    data: RecitationCreateIn,
) -> tuple[int, Asset]:
    logger.info(
        f"Creating recitation [publisher_id={data.publisher_id}, reciter_id={data.reciter_id}, user_id={request.user.id}]"
    )
    enforce_publisher_membership(request.user, data.publisher_id)
    service = RecitationService()
    recitation = service.create_recitation(
        publisher_id=data.publisher_id,
        name_ar=data.name_ar,
        name_en=data.name_en,
        description_ar=data.description_ar,
        description_en=data.description_en,
        license=data.license,
        reciter_id=data.reciter_id,
        qiraah_id=data.qiraah_id,
        riwayah_id=data.riwayah_id,
        madd_level=data.madd_level,
        meem_behaviour=data.meem_behaviour,
        year=data.year,
    )
    logger.info(f"Recitation created [recitation_id={recitation.id}, user_id={request.user.id}]")
    return 201, recitation


@router.get(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
def retrieve_recitation(request: Request, recitation_slug: str) -> Asset:
    try:
        return (
            Asset.objects.select_related("publisher", "reciter", "riwayah", "qiraah")
            .prefetch_related("versions")
            .filter(request.user_publisher_q())
            .get(slug=recitation_slug, category=CategoryChoice.RECITATION)
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="recitation_not_found",
            message=_("Recitation with slug {slug} not found.").format(slug=recitation_slug),
            status_code=404,
        ) from exc


@router.put(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        400: NinjaErrorResponse[Literal["recitation_name_required"]]
        | NinjaErrorResponse[Literal["invalid_riwayah_qiraah_combo"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]]
        | NinjaErrorResponse[Literal["publisher_not_found"]]
        | NinjaErrorResponse[Literal["reciter_not_found"]]
        | NinjaErrorResponse[Literal["qiraah_not_found"]]
        | NinjaErrorResponse[Literal["riwayah_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)])
def update_recitation_put(
    request: Request,
    recitation_slug: str,
    data: RecitationPutIn,
) -> Asset:
    logger.info(f"Updating recitation (PUT) [recitation_slug={recitation_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = RecitationService()
    fields = data.model_dump()
    recitation = service.update_recitation(recitation_slug, fields=fields, user_publisher_q=request.user_publisher_q())
    logger.info(f"Recitation updated [recitation_id={recitation.id}, user_id={request.user.id}]")
    return recitation


@router.patch(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        400: NinjaErrorResponse[Literal["recitation_name_required"]]
        | NinjaErrorResponse[Literal["invalid_riwayah_qiraah_combo"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]]
        | NinjaErrorResponse[Literal["publisher_not_found"]]
        | NinjaErrorResponse[Literal["reciter_not_found"]]
        | NinjaErrorResponse[Literal["qiraah_not_found"]]
        | NinjaErrorResponse[Literal["riwayah_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)])
def update_recitation_patch(
    request: Request,
    recitation_slug: str,
    data: RecitationPatchIn,
) -> Asset:
    logger.info(f"Updating recitation (PATCH) [recitation_slug={recitation_slug}, user_id={request.user.id}]")
    if data.publisher_id is not None:
        enforce_publisher_membership(request.user, data.publisher_id)
    service = RecitationService()
    fields = data.model_dump(exclude_unset=True)
    recitation = service.update_recitation(recitation_slug, fields=fields, user_publisher_q=request.user_publisher_q())
    logger.info(f"Recitation updated [recitation_id={recitation.id}, user_id={request.user.id}]")
    return recitation


@router.delete(
    "recitations/{recitation_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_RECITATION)])
def delete_recitation(request: Request, recitation_slug: str) -> tuple[int, None]:
    logger.info(f"Deleting recitation [recitation_slug={recitation_slug}, user_id={request.user.id}]")
    service = RecitationService()
    service.delete_recitation(recitation_slug, user_publisher_q=request.user_publisher_q())
    logger.info(f"Recitation deleted [recitation_slug={recitation_slug}, user_id={request.user.id}]")
    return 204, None
