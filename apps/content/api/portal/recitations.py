from typing import Annotated, Literal

from ninja import Field, FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import Asset, LicenseChoice
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


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
    publisher: PublisherRef = Field(alias="resource.publisher")
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
    publisher: PublisherRef = Field(alias="resource.publisher")
    reciter: MinimalReciter | None = None
    qiraah: MinimalQiraah | None = None
    riwayah: MinimalRiwayah | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None


# --- Input Schemas ---


class RecitationCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str = ""
    description_en: str = ""
    publisher_id: int = Field(...)
    reciter_id: int = Field(...)
    qiraah_id: int | None = None
    riwayah_id: int | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice = Field(...)


class RecitationPutIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str = ""
    description_en: str = ""
    publisher_id: int = Field(...)
    reciter_id: int = Field(...)
    qiraah_id: int | None = None
    riwayah_id: int | None = None
    madd_level: Asset.MaddLevelChoice | None = None
    meem_behaviour: Asset.MeemBehaviourChoice | None = None
    year: int | None = None
    license: LicenseChoice = Field(...)


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
    publisher_id: Annotated[list[int] | None, FilterLookup(q="resource__publisher_id__in")] = None
    reciter_id: Annotated[list[int] | None, FilterLookup(q="reciter_id__in")] = None
    qiraah_id: Annotated[list[int] | None, FilterLookup(q="qiraah_id__in")] = None
    riwayah_id: Annotated[list[int] | None, FilterLookup(q="riwayah_id__in")] = None
    madd_level: Annotated[list[Asset.MaddLevelChoice] | None, FilterLookup(q="madd_level__in")] = None
    meem_behaviour: Annotated[list[Asset.MeemBehaviourChoice] | None, FilterLookup(q="meem_behaviour__in")] = None
    year: Annotated[int | None, FilterLookup(q="year")] = None
    license_code: Annotated[list[LicenseChoice] | None, FilterLookup(q="license__in")] = None


# --- Endpoints ---


@router.get("recitations/", response=list[RecitationListOut])
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
        "resource__publisher__name",
        "reciter__name",
    ]
)
def list_recitations(request: Request, filters: RecitationFilter = Query()):
    service = RecitationService()
    qs = service.get_all_recitations(None, filters)
    return qs


@router.post(
    "recitations/",
    response={
        201: RecitationDetailOut,
        400: NinjaErrorResponse[
            Literal["recitation_name_required", "invalid_riwayah_qiraah_combo"],
            Literal[None],
        ],
        404: NinjaErrorResponse[
            Literal[
                "publisher_not_found",
                "reciter_not_found",
                "qiraah_not_found",
                "riwayah_not_found",
            ],
            Literal[None],
        ],
    },
)
def create_recitation(
    request: Request,
    data: RecitationCreateIn,
) -> tuple[int, Asset]:
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
    return 201, recitation


@router.get(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        404: NinjaErrorResponse[Literal["recitation_not_found"], Literal[None]],
    },
)
def retrieve_recitation(request: Request, recitation_slug: str) -> Asset:
    service = RecitationService()
    return service.get_recitation(recitation_slug)


@router.put(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        400: NinjaErrorResponse[
            Literal["recitation_name_required", "invalid_riwayah_qiraah_combo"],
            Literal[None],
        ],
        404: NinjaErrorResponse[
            Literal[
                "recitation_not_found",
                "publisher_not_found",
                "reciter_not_found",
                "qiraah_not_found",
                "riwayah_not_found",
            ],
            Literal[None],
        ],
    },
)
def update_recitation_put(
    request: Request,
    recitation_slug: str,
    data: RecitationPutIn,
) -> Asset:
    service = RecitationService()
    fields = data.model_dump()
    recitation = service.update_recitation(recitation_slug, fields=fields)
    return recitation


@router.patch(
    "recitations/{recitation_slug}/",
    response={
        200: RecitationDetailOut,
        400: NinjaErrorResponse[
            Literal["recitation_name_required", "invalid_riwayah_qiraah_combo"],
            Literal[None],
        ],
        404: NinjaErrorResponse[
            Literal[
                "recitation_not_found",
                "publisher_not_found",
                "reciter_not_found",
                "qiraah_not_found",
                "riwayah_not_found",
            ],
            Literal[None],
        ],
    },
)
def update_recitation_patch(
    request: Request,
    recitation_slug: str,
    data: RecitationPatchIn,
) -> Asset:
    service = RecitationService()
    fields = data.model_dump(exclude_unset=True)
    recitation = service.update_recitation(recitation_slug, fields=fields)
    return recitation


@router.delete(
    "recitations/{recitation_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["recitation_not_found"], Literal[None]],
    },
)
def delete_recitation(request: Request, recitation_slug: str) -> tuple[int, None]:
    service = RecitationService()
    service.delete_recitation(recitation_slug)
    return 204, None
