"""
Qiraahs CRUD endpoints for CMS internal API.

POST   /cms-api/qiraahs/create/         → Create a new qiraah
GET    /cms-api/qiraahs/{id}/            → Qiraah detail
PUT    /cms-api/qiraahs/{id}/update/     → Full update a qiraah
PATCH  /cms-api/qiraahs/{id}/update/     → Partial update a qiraah
DELETE /cms-api/qiraahs/{id}/delete/     → Delete a qiraah
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.content.models import Qiraah
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.QIRAAHS])


# ── Schemas ─────────────────────────────────────────────────────────


class QiraahCreateIn(Schema):
    """Payload for creating a new qiraah."""

    name: str = Field(min_length=1, description="Qiraah name / اسم القراءة")
    name_ar: str | None = None
    bio: str = ""
    recitation_style: str | None = Field(
        None, description="Recitation style: murattal (مرتل) or mujawwad (مجود)"
    )


class QiraahCreateOut(Schema):
    """Response after creating a qiraah."""

    id: int
    name: str
    slug: str


class QiraahDetailOut(Schema):
    """Full qiraah detail response."""

    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    recitation_style: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class QiraahUpdateIn(Schema):
    """Payload for updating a qiraah (full or partial)."""

    name: str | None = Field(None, min_length=1, description="Qiraah name / اسم القراءة")
    name_ar: str | None = None
    bio: str | None = None
    is_active: bool | None = None
    recitation_style: str | None = Field(
        None, description="Recitation style: murattal (مرتل) or mujawwad (مجود)"
    )


class QiraahUpdateOut(Schema):
    """Response after updating a qiraah."""

    id: int
    name: str
    slug: str
    bio: str
    is_active: bool
    recitation_style: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("qiraahs/create/", response={201: QiraahCreateOut})
def create_qiraah(request: Request, payload: QiraahCreateIn):
    """
    CMS Internal API: Create a new qiraah (إضافة قراءة).
    """
    qiraah = Qiraah(
        name=payload.name,
        bio=payload.bio,
        recitation_style=payload.recitation_style,
    )
    if payload.name_ar:
        qiraah.name_ar = payload.name_ar
    qiraah.save()

    return 201, qiraah


@router.get("qiraahs/{id}/", response=QiraahDetailOut)
def detail_qiraah(request: Request, id: int):
    """
    CMS Internal API: Get qiraah detail (تفاصيل القراءة).
    """
    qiraah = get_object_or_404(Qiraah, id=id)
    return qiraah


@router.put("qiraahs/{id}/update/", response=QiraahUpdateOut)
def update_qiraah(request: Request, id: int, data: QiraahUpdateIn):
    """
    CMS Internal API: Full update a qiraah (تعديل قراءة).
    """
    qiraah = get_object_or_404(Qiraah, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(qiraah, field, value)

    qiraah.save()
    return qiraah


@router.patch("qiraahs/{id}/update/", response=QiraahUpdateOut)
def partial_update_qiraah(request: Request, id: int, data: QiraahUpdateIn):
    """
    CMS Internal API: Partial update a qiraah (تعديل جزئي لقراءة).
    """
    qiraah = get_object_or_404(Qiraah, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(qiraah, field, value)

    qiraah.save()
    return qiraah


@router.delete("qiraahs/{id}/delete/", response=OkSchema)
def delete_qiraah(request: Request, id: int):
    """
    CMS Internal API: Delete a qiraah (حذف قراءة).
    """
    qiraah = get_object_or_404(Qiraah, id=id)
    qiraah.delete()
    return OkSchema(message=_("Qiraah deleted successfully."))
