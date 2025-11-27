from django.shortcuts import get_object_or_404
from ninja import Schema
from pydantic import field_serializer
from pydantic_core.core_schema import SerializationInfo

from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class DetailPublisherOut(Schema):
    id: int
    name: str
    slug: str
    description: str
    address: str
    website: str
    is_verified: bool
    contact_email: str
    icon_url: str | None

    @field_serializer("icon_url")
    def serialize_icon_url(self, value, info: SerializationInfo) -> str:
        request = info.context.get("request")
        if request and isinstance(value, str) and not value.startswith("https"):
            return request.build_absolute_uri(value)

        return value if isinstance(value, str) else ""


@router.get("publishers/{id}/", response=DetailPublisherOut, auth=None)
def detail_publishers(request: Request, id: int):
    publisher = get_object_or_404(Publisher, id=id)
    return publisher
