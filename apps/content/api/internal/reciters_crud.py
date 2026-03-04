"""
Reciters CRUD endpoints for CMS internal API.

GET    /cms-api/reciters/{id}/      → Reciter detail (already in reciter_profile.py)
PUT    /cms-api/reciters/{id}/update/   → Full update a reciter
PATCH  /cms-api/reciters/{id}/update/   → Partial update a reciter
DELETE /cms-api/reciters/{id}/delete/   → Delete a reciter
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.content.models import Reciter
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.ninja_utils.types import AbsoluteUrl

router = ItqanRouter(tags=[NinjaTag.RECITERS])


# ── Schemas ─────────────────────────────────────────────────────────


class ReciterDetailOut(Schema):
    """Full reciter detail response."""

    id: int
    name: str
    slug: str
    bio: str
    image_url: AbsoluteUrl | None
    is_active: bool 
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ReciterUpdateIn(Schema):
    """Payload for updating a reciter (full or partial)."""

    name: str | None = Field(None, min_length=1, description="Reciter name")
    name_ar: str | None = None
    bio: str | None = None
    is_active: bool | None = None


class ReciterUpdateOut(Schema):
    """Response after updating a reciter."""

    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


# ── Endpoints ───────────────────────────────────────────────────────


@router.put("reciters/{id}/update/", response=ReciterUpdateOut)
def update_reciter(request: Request, id: int, data: ReciterUpdateIn):
    """
    CMS Internal API: Full update a reciter (تعديل قارئ).
    """
    reciter = get_object_or_404(Reciter, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(reciter, field, value)

    reciter.save()
    return reciter


@router.patch("reciters/{id}/update/", response=ReciterUpdateOut)
def partial_update_reciter(request: Request, id: int, data: ReciterUpdateIn):
    """
    CMS Internal API: Partial update a reciter (تعديل جزئي لقارئ).
    """
    reciter = get_object_or_404(Reciter, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(reciter, field, value)

    reciter.save()
    return reciter


@router.delete("reciters/{id}/delete/", response=OkSchema)
def delete_reciter(request: Request, id: int):
    """
    CMS Internal API: Delete a reciter (حذف قارئ).
    """
    reciter = get_object_or_404(Reciter, id=id)
    reciter.delete()
    return OkSchema(message=_("Reciter deleted successfully."))
