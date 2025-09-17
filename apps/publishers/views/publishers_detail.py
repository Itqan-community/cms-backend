from typing import Any
from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.content.models import Publisher
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class DetailPublisherOut(Schema):
    id: UUID
    name: str
    slug: str
    summary: str
    description: str
    location: str
    website: str
    verified: bool
    contact_email: str
    icon_url: str | None
    social_links: dict[str, Any]


@router.get("content/publishers/{id}/", response=DetailPublisherOut)
def detail_publishers(request, id: UUID):
    publisher = get_object_or_404(Publisher, id=id)
    return publisher
