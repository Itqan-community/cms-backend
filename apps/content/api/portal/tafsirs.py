from typing import Annotated, Literal

from ninja import FilterLookup, FilterSchema, Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, LicenseChoice, ResourceVersion
from apps.content.services.tafsir import TafsirService
from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.TAFSIRS])


# --- Output Schemas ---


class TafsirPublisherOut(Schema):
    id: int
    name: str


class TafsirListOut(Schema):
    id: int
    name: str
    description: str
    publisher: TafsirPublisherOut
    license: LicenseChoice
    is_external: bool
    created_at: AwareDatetime

    @staticmethod
    def resolve_publisher(obj: Asset) -> TafsirPublisherOut:
        return TafsirPublisherOut(id=obj.resource.publisher.id, name=obj.resource.publisher.name)


class TafsirVersionOut(Schema):
    id: int
    name: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_file_url(obj: ResourceVersion) -> str | None:
        if obj.storage_url:
            return obj.storage_url.url
        return None


class TafsirDetailOut(Schema):
    id: int
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    long_description_ar: str | None = None
    long_description_en: str | None = None
    thumbnail_url: str | None = None
    publisher: TafsirPublisherOut
    license: LicenseChoice
    is_external: bool
    external_url: str | None = None
    versions: list[TafsirVersionOut]
    created_at: AwareDatetime

    @staticmethod
    def resolve_thumbnail_url(obj: Asset) -> str | None:
        if obj.thumbnail_url:
            return obj.thumbnail_url.url
        return None

    @staticmethod
    def resolve_publisher(obj: Asset) -> TafsirPublisherOut:
        return TafsirPublisherOut(id=obj.resource.publisher.id, name=obj.resource.publisher.name)

    @staticmethod
    def resolve_versions(obj: Asset) -> list[TafsirVersionOut]:
        return list(obj.resource.versions.all())


# --- Input Schemas ---


class TafsirCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str = ""
    description_en: str = ""
    long_description_ar: str = ""
    long_description_en: str = ""
    license: LicenseChoice = Field(...)
    language: str = Field(..., max_length=10)
    publisher_id: int = Field(...)
    is_external: bool = False
    external_url: str | None = None


class TafsirPutIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)
    description_ar: str = ""
    description_en: str = ""
    long_description_ar: str = ""
    long_description_en: str = ""
    license: LicenseChoice = Field(...)
    language: str = Field(..., max_length=10)
    publisher_id: int = Field(...)
    is_external: bool = False
    external_url: str | None = None


class TafsirPatchIn(Schema):
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


# --- Filter Schema ---


class TafsirFilter(FilterSchema):
    publisher_id: Annotated[list[int] | None, FilterLookup(q="resource__publisher_id__in")] = None
    license_code: Annotated[list[str] | None, FilterLookup(q="license__in")] = None
    language: Annotated[str | None, FilterLookup(q="language")] = None
    is_external: Annotated[bool | None, FilterLookup(q="resource__is_external")] = None


# --- Endpoints ---


@router.get("tafsirs/", response=list[TafsirListOut])
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
        "resource__publisher__name",
    ]
)
def list_tafsirs(request: Request, filters: TafsirFilter = Query()):
    service = TafsirService()
    qs = service.get_all_tafsirs(filters)
    return qs


@router.post(
    "tafsirs/",
    response={
        201: TafsirDetailOut,
        400: NinjaErrorResponse[Literal["tafsir_name_required"], Literal[None]],
        404: NinjaErrorResponse[Literal["publisher_not_found"], Literal[None]]
        | NinjaErrorResponse[Literal["tafsir_not_found"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def create_tafsir(
    request: Request,
    data: TafsirCreateIn,
) -> tuple[int, Asset]:
    service = TafsirService()
    tafsir = service.create_tafsir(
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
    return 201, tafsir


@router.get(
    "tafsirs/{tafsir_slug}/",
    response={
        200: TafsirDetailOut,
        404: NinjaErrorResponse[Literal["tafsir_not_found"], Literal[None]],
    },
)
def retrieve_tafsir(request: Request, tafsir_slug: str) -> Asset:
    service = TafsirService()
    return service.get_tafsir(tafsir_slug)


@router.put(
    "tafsirs/{tafsir_slug}/",
    response={
        200: TafsirDetailOut,
        400: NinjaErrorResponse[Literal["tafsir_name_required"], Literal[None]],
        404: NinjaErrorResponse[Literal["tafsir_not_found"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def update_tafsir_put(
    request: Request,
    tafsir_slug: str,
    data: TafsirPutIn,
) -> Asset:
    service = TafsirService()
    fields = data.model_dump()
    tafsir = service.update_tafsir(tafsir_slug, fields=fields)
    return tafsir


@router.patch(
    "tafsirs/{tafsir_slug}/",
    response={
        200: TafsirDetailOut,
        400: NinjaErrorResponse[Literal["tafsir_name_required"], Literal[None]],
        404: NinjaErrorResponse[Literal["tafsir_not_found"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def update_tafsir_patch(
    request: Request,
    tafsir_slug: str,
    data: TafsirPatchIn,
) -> Asset:
    service = TafsirService()
    fields = data.model_dump(exclude_unset=True)
    tafsir = service.update_tafsir(tafsir_slug, fields=fields)
    return tafsir


@router.delete(
    "tafsirs/{tafsir_slug}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["tafsir_not_found"], Literal[None]],
    },
    auth=ninja_jwt_auth,
)
def delete_tafsir(request: Request, tafsir_slug: str) -> tuple[int, None]:
    service = TafsirService()
    service.delete_tafsir(tafsir_slug)
    return 204, None
