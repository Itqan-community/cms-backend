from django.db import IntegrityError
from ninja import Schema
from pydantic import Field

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherCreateIn(Schema):
    name: str
    name_ar: str = ""
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
    name_ar: str
    slug: str
    description: str
    description_ar: str
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None
    country: str
    created_at: str

    @staticmethod
    def resolve_created_at(obj: Publisher) -> str:
        return obj.created_at.isoformat() if obj.created_at else ""


@router.post("publishers/", response={201: PublisherCreateOut, 400: NinjaErrorResponse})
def create_publisher(request: Request, payload: PublisherCreateIn):
    if not payload.name or not payload.name.strip():
        raise ItqanError("publisher_name_required", "Publisher name is required")

    try:
        publisher = Publisher.objects.create(
            name=payload.name.strip(),
            name_ar=payload.name_ar,
            description=payload.description,
            description_ar=payload.description_ar,
            address=payload.address,
            website=payload.website,
            contact_email=payload.contact_email,
            is_verified=payload.is_verified,
            foundation_year=payload.foundation_year,
            country=payload.country,
        )
    except IntegrityError as err:
        raise ItqanError("publisher_already_exists", "A publisher with this name already exists") from err

    return 201, publisher
