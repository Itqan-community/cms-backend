from ninja import File, FilterSchema, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher
from apps.publishers.repositories.publisher import PublisherRepository
from apps.publishers.services.publisher import PublisherService

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherCreateIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    address: str = ""
    website: str = ""
    contact_email: str = ""
    is_verified: bool = True
    foundation_year: int | None = None
    country: str = ""


class PublisherCreateOut(Schema):
    id: int
    name: str
    slug: str
    name_ar: str | None
    name_en: str | None
    description_en: str | None
    description_ar: str | None
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None
    country: str
    icon_url: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @staticmethod
    def resolve_icon_url(obj: Publisher) -> str | None:
        if obj.icon_url:
            return obj.icon_url.url
        return None


@router.post("publishers/", response={201: PublisherCreateOut, 400: NinjaErrorResponse})
def create_publisher(
    request: Request, data: Form[PublisherCreateIn], icon: UploadedFile = File(None)
) -> tuple[int, Publisher]:
    service = PublisherService(PublisherRepository())
    publisher = service.create_publisher(
        name_ar=data.name_ar,
        name_en=data.name_en,
        description_ar=data.description_ar,
        description_en=data.description_en,
        address=data.address,
        website=data.website,
        contact_email=data.contact_email,
        is_verified=data.is_verified,
        foundation_year=data.foundation_year,
        country=data.country,
        icon_url=icon,
    )
    return 201, publisher


# --- List Publishers ---


class PublisherListOut(Schema):
    id: int
    name: str
    slug: str
    is_verified: bool
    country: str
    foundation_year: int | None
    icon_url: str | None = None
    created_at: AwareDatetime

    @staticmethod
    def resolve_icon_url(obj: Publisher) -> str | None:
        if obj.icon_url:
            return obj.icon_url.url
        return None


class PublisherFilter(FilterSchema):
    is_verified: bool | None = None
    country: str | None = None


@router.get("publishers/", response=list[PublisherListOut])
@paginate
@ordering(ordering_fields=["name", "created_at", "foundation_year"])
@searching(search_fields=["name_en", "name_ar", "description_en", "description_ar"])
def list_publishers(request: Request, filters: PublisherFilter = Query(...)):
    qs = Publisher.objects.all()
    qs = filters.filter(qs)
    return qs


# --- Retrieve Publisher ---


class PublisherDetailOut(Schema):
    id: int
    name: str
    slug: str
    name_ar: str | None
    name_en: str | None
    description: str
    description_ar: str | None
    description_en: str | None
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None
    country: str
    icon_url: str | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @staticmethod
    def resolve_icon_url(obj: Publisher) -> str | None:
        if obj.icon_url:
            return obj.icon_url.url
        return None


@router.get(
    "publishers/{int:publisher_id}/",
    response={200: PublisherDetailOut, 404: NinjaErrorResponse},
)
def retrieve_publisher(request: Request, publisher_id: int) -> Publisher:
    service = PublisherService(PublisherRepository())
    return service.get_publisher(publisher_id)


# --- Update Publisher ---


class PublisherPatchIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    address: str | None = None
    website: str | None = None
    contact_email: str | None = None
    is_verified: bool | None = None
    foundation_year: int | None = None
    country: str | None = None


class PublisherPutIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    description_ar: str | None = None
    description_en: str | None = None
    address: str = ""
    website: str = ""
    contact_email: str = ""
    is_verified: bool = True
    foundation_year: int | None = None
    country: str = ""


@router.put(
    "publishers/{int:publisher_id}/",
    response={200: PublisherDetailOut, 400: NinjaErrorResponse, 404: NinjaErrorResponse},
)
def update_publisher_put(
    request: Request, publisher_id: int, data: Form[PublisherPutIn], icon: UploadedFile = File(None)
) -> Publisher:
    service = PublisherService(PublisherRepository())
    fields = data.model_dump()
    if icon:
        fields["icon_url"] = icon
    return service.update_publisher(publisher_id, fields=fields)


@router.patch(
    "publishers/{int:publisher_id}/",
    response={200: PublisherDetailOut, 400: NinjaErrorResponse, 404: NinjaErrorResponse},
)
def update_publisher_patch(
    request: Request, publisher_id: int, data: Form[PublisherPatchIn], icon: UploadedFile = File(None)
) -> Publisher:
    service = PublisherService(PublisherRepository())
    fields = data.model_dump(exclude_unset=True)
    if icon:
        fields["icon_url"] = icon
    return service.update_publisher(publisher_id, fields=fields)


# --- Delete Publisher ---


@router.delete(
    "publishers/{int:publisher_id}/",
    response={204: None, 404: NinjaErrorResponse},
)
def delete_publisher(request: Request, publisher_id: int) -> tuple[int, None]:
    service = PublisherService(PublisherRepository())
    service.delete_publisher(publisher_id)
    return 204, None
