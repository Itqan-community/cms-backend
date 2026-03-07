from ninja import Schema

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherDetailOut(Schema):
    id: int
    name: str
    name_ar: str
    name_en: str
    slug: str
    description: str
    description_ar: str
    description_en: str
    address: str
    website: str
    contact_email: str
    is_verified: bool
    foundation_year: int | None
    country: str
    icon_url: str

    created_at: str
    updated_at: str

    @staticmethod
    def resolve_icon_url(obj: Publisher) -> str:
        return obj.icon_url.url if obj.icon_url else ""

    @staticmethod
    def resolve_created_at(obj: Publisher) -> str:
        return obj.created_at.isoformat() if obj.created_at else ""

    @staticmethod
    def resolve_updated_at(obj: Publisher) -> str:
        return obj.updated_at.isoformat() if obj.updated_at else ""


@router.get("publishers/{id}/", response={200: PublisherDetailOut, 404: NinjaErrorResponse})
def retrieve_publisher(request: Request, id: int):
    try:
        publisher = Publisher.objects.get(id=id)
    except Publisher.DoesNotExist as err:
        raise ItqanError("publisher_not_found", "Publisher not found", status_code=404) from err

    return publisher
