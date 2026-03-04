"""
Riwayahs CRUD endpoints for CMS internal API.

POST   /cms-api/riwayahs/create/         → Create a new riwayah
GET    /cms-api/riwayahs/{id}/            → Riwayah detail
PUT    /cms-api/riwayahs/{id}/update/     → Full update a riwayah
PATCH  /cms-api/riwayahs/{id}/update/     → Partial update a riwayah
DELETE /cms-api/riwayahs/{id}/delete/     → Delete a riwayah
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _

from ninja import Schema
from pydantic import AwareDatetime, Field

from apps.content.models import Riwayah
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.schemas import OkSchema
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RIWAYAHS])


# ── Schemas ─────────────────────────────────────────────────────────


class RiwayahQiraahOut(Schema):
    """Nested qiraah info in riwayah response."""

    id: int
    name: str
    slug: str


class RiwayahCreateIn(Schema):
    """Payload for creating a new riwayah."""

    name: str = Field(min_length=1, description="Riwayah name / اسم الرواية")
    name_ar: str | None = None
    qiraah_id: int = Field(description="Parent Qiraah ID / رقم القراءة")


class RiwayahCreateOut(Schema):
    """Response after creating a riwayah."""

    id: int
    name: str
    slug: str
    qiraah: RiwayahQiraahOut


class RiwayahDetailOut(Schema):
    """Full riwayah detail response."""

    id: int
    name: str
    slug: str
    is_active: bool
    qiraah: RiwayahQiraahOut
    created_at: AwareDatetime
    updated_at: AwareDatetime


class RiwayahUpdateIn(Schema):
    """Payload for updating a riwayah (full or partial)."""

    name: str | None = Field(None, min_length=1, description="Riwayah name / اسم الرواية")
    name_ar: str | None = None
    qiraah_id: int | None = None
    is_active: bool | None = None


class RiwayahUpdateOut(Schema):
    """Response after updating a riwayah."""

    id: int
    name: str
    slug: str
    is_active: bool
    qiraah: RiwayahQiraahOut
    created_at: AwareDatetime
    updated_at: AwareDatetime


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("riwayahs/create/", response={201: RiwayahCreateOut})
def create_riwayah(request: Request, payload: RiwayahCreateIn):
    """
    CMS Internal API: Create a new riwayah (إضافة رواية).
    """
    riwayah = Riwayah(
        name=payload.name,
        qiraah_id=payload.qiraah_id,
    )
    if payload.name_ar:
        riwayah.name_ar = payload.name_ar
    riwayah.save()

    # Reload with qiraah relation for response
    riwayah = Riwayah.objects.select_related("qiraah").get(id=riwayah.id)
    return 201, riwayah


@router.get("riwayahs/{id}/", response=RiwayahDetailOut)
def detail_riwayah(request: Request, id: int):
    """
    CMS Internal API: Get riwayah detail (تفاصيل الرواية).
    """
    riwayah = get_object_or_404(Riwayah.objects.select_related("qiraah"), id=id)
    return riwayah


@router.put("riwayahs/{id}/update/", response=RiwayahUpdateOut)
def update_riwayah(request: Request, id: int, data: RiwayahUpdateIn):
    """
    CMS Internal API: Full update a riwayah (تعديل رواية).
    """
    riwayah = get_object_or_404(Riwayah, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(riwayah, field, value)

    riwayah.save()

    # Reload with qiraah relation for response
    riwayah = Riwayah.objects.select_related("qiraah").get(id=riwayah.id)
    return riwayah


@router.patch("riwayahs/{id}/update/", response=RiwayahUpdateOut)
def partial_update_riwayah(request: Request, id: int, data: RiwayahUpdateIn):
    """
    CMS Internal API: Partial update a riwayah (تعديل جزئي لرواية).
    """
    riwayah = get_object_or_404(Riwayah, id=id)

    for field, value in data.dict(exclude_unset=True).items():
        setattr(riwayah, field, value)

    riwayah.save()

    # Reload with qiraah relation for response
    riwayah = Riwayah.objects.select_related("qiraah").get(id=riwayah.id)
    return riwayah


@router.delete("riwayahs/{id}/delete/", response=OkSchema)
def delete_riwayah(request: Request, id: int):
    """
    CMS Internal API: Delete a riwayah (حذف رواية).
    """
    riwayah = get_object_or_404(Riwayah, id=id)
    riwayah.delete()
    return OkSchema(message=_("Riwayah deleted successfully."))
