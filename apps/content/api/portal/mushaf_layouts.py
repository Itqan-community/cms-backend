import logging
from typing import Literal

from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import MushafLayout
from apps.content.services.mushaf_layout import MushafLayoutService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.MUSHAF_LAYOUTS])
logger = logging.getLogger(__name__)


class MushafLayoutOut(Schema):
    id: int
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int
    assets_count: int = Field(0, description="Number of assets using this layout")
    created_at: AwareDatetime
    updated_at: AwareDatetime


class MushafLayoutCreateIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int = Field(..., ge=1)


class MushafLayoutPatchIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int | None = Field(default=None, ge=1)


@router.get("mushaf-layouts/", response=list[MushafLayoutOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)])
@paginate
@ordering(ordering_fields=["name", "page_count", "created_at"])
@searching(search_fields=["name_ar", "name_en"])
def list_mushaf_layouts(request: Request):
    return MushafLayout.objects.annotate(assets_count=Count("assets"))


@router.get(
    "mushaf-layouts/{layout_id}/",
    response={
        200: MushafLayoutOut,
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)])
def retrieve_mushaf_layout(request: Request, layout_id: int):
    try:
        return MushafLayout.objects.annotate(assets_count=Count("assets")).get(pk=layout_id)
    except MushafLayout.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_layout_not_found",
            message=_("Mushaf layout with id {id} not found.").format(id=layout_id),
            status_code=404,
        ) from exc


@router.post(
    "mushaf-layouts/",
    response={
        201: MushafLayoutOut,
        400: NinjaErrorResponse[Literal["mushaf_layout_name_required"]],
        409: NinjaErrorResponse[Literal["mushaf_layout_already_exists"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT)])
def create_mushaf_layout(request: Request, data: MushafLayoutCreateIn):
    layout = MushafLayoutService().create(name_ar=data.name_ar, name_en=data.name_en, page_count=data.page_count)
    return 201, layout


@router.patch(
    "mushaf-layouts/{layout_id}/",
    response={
        200: MushafLayoutOut,
        400: NinjaErrorResponse[Literal["mushaf_layout_name_required"]],
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
        409: NinjaErrorResponse[Literal["mushaf_layout_already_exists"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT)])
def update_mushaf_layout(request: Request, layout_id: int, data: MushafLayoutPatchIn):
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    return MushafLayoutService().update(layout_id, **fields)


@router.delete(
    "mushaf-layouts/{layout_id}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["mushaf_layout_in_use"]],
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT)])
def delete_mushaf_layout(request: Request, layout_id: int):
    MushafLayoutService().delete(layout_id)
    return 204, None
