from ninja import Schema
from pydantic import AwareDatetime

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.repositories.publisher import PublisherRepository
from apps.publishers.services.publisher import PublisherService

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherCreateIn(Schema):
    name: str
    name_ar: str = ""
    name_en: str = ""
    description: str = ""
    description_ar: str = ""
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
    description: str
    description_ar: str | None
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None
    country: str
    created_at: AwareDatetime
    updated_at: AwareDatetime


@router.post(
    "publishers/",
    response={201: PublisherCreateOut, 400: NinjaErrorResponse},
    auth=ninja_jwt_auth,
)
def create_publisher(request: Request, data: PublisherCreateIn) -> tuple[int, object]:
    service = PublisherService(PublisherRepository())
    publisher = service.create_publisher(
        name=data.name,
        name_ar=data.name_ar,
        name_en=data.name_en,
        description=data.description,
        description_ar=data.description_ar,
        address=data.address,
        website=data.website,
        contact_email=data.contact_email,
        is_verified=data.is_verified,
        foundation_year=data.foundation_year,
        country=data.country,
    )
    return 201, publisher
