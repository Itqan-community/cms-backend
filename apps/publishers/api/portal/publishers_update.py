from django.db import IntegrityError
from ninja import Schema

from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


class PublisherUpdateIn(Schema):
    name: str | None = None
    name_ar: str | None = None
    description: str | None = None
    description_ar: str | None = None
    address: str | None = None
    website: str | None = None
    contact_email: str | None = None
    is_verified: bool | None = None
    foundation_year: int | None = None
    country: str | None = None


class PublisherUpdateOut(Schema):
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
    updated_at: str

    @staticmethod
    def resolve_created_at(obj: Publisher) -> str:
        return obj.created_at.isoformat() if obj.created_at else ""

    @staticmethod
    def resolve_updated_at(obj: Publisher) -> str:
        return obj.updated_at.isoformat() if obj.updated_at else ""


def _get_publisher_or_404(id: int) -> Publisher:
    try:
        return Publisher.objects.get(id=id)
    except Publisher.DoesNotExist:
        raise ItqanError("publisher_not_found", "Publisher not found", status_code=404)


def _apply_update(publisher: Publisher, payload: PublisherUpdateIn, partial: bool = False) -> Publisher:
    fields = payload.dict(exclude_unset=partial)
    for field, value in fields.items():
        if value is not None or not partial:
            setattr(publisher, field, value if value is not None else "")
    try:
        publisher.save()
    except IntegrityError:
        raise ItqanError("publisher_already_exists", "A publisher with this name already exists")
    return publisher


@router.put("publishers/{id}/", response=PublisherUpdateOut)
def update_publisher(request: Request, id: int, payload: PublisherUpdateIn):
    publisher = _get_publisher_or_404(id)
    if payload.name is not None and not payload.name.strip():
        raise ItqanError("publisher_name_required", "Publisher name is required")
    _apply_update(publisher, payload, partial=False)
    return publisher


@router.patch("publishers/{id}/", response=PublisherUpdateOut)
def patch_publisher(request: Request, id: int, payload: PublisherUpdateIn):
    publisher = _get_publisher_or_404(id)
    if payload.name is not None and not payload.name.strip():
        raise ItqanError("publisher_name_required", "Publisher name is required")
    _apply_update(publisher, payload, partial=True)
    return publisher
