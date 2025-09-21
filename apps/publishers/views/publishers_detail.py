from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.publishers.models import Publisher
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.request import Request

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


@router.get("publishers/{id}/", response=DetailPublisherOut, auth=None)
def detail_publishers(request: Request, id: int):
    publisher = get_object_or_404(Publisher, id=id)
    return publisher
