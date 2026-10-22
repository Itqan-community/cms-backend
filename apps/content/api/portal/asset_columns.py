"""Portal endpoints for the text columns of translations and tafsirs.

Anyone who may read the asset sees its columns; adding, labelling, reordering
and deleting them takes ``PORTAL_MANAGE_ASSET_COLUMNS`` plus access to every
language, because a column applies to all of the asset's languages.
"""

from typing import Literal

from ninja import Schema
from pydantic import Field

from apps.content.api.portal.asset_content import _resolve
from apps.content.models import Asset, AssetColumn, CategoryChoice
from apps.content.services.asset_columns import AssetColumnService
from apps.content.services.asset_content import AssetContentService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class AssetColumnOut(Schema):
    key: str
    label_en: str
    label_ar: str
    order: int
    committed: bool = Field(
        ..., description="A committed version contains this column: its key is frozen and it can't be deleted."
    )

    @staticmethod
    def resolve_label_en(obj: AssetColumn) -> str:
        return obj.label_en or ""

    @staticmethod
    def resolve_label_ar(obj: AssetColumn) -> str:
        return obj.label_ar or ""

    @staticmethod
    def resolve_committed(obj: AssetColumn, context: dict) -> bool:
        # One query per request, not per column.
        cache = context["request"].__dict__.setdefault("_committed_column_keys", {})
        if obj.asset_id not in cache:
            cache[obj.asset_id] = AssetColumnService().committed_keys(obj.asset)
        return obj.key in cache[obj.asset_id]


class AssetColumnIn(Schema):
    key: str = Field(..., max_length=64)
    label_en: str = Field(default="", max_length=255)
    label_ar: str = Field(default="", max_length=255)


class AssetColumnPatchIn(Schema):
    key: str | None = Field(default=None, max_length=64)
    label_en: str | None = Field(default=None, max_length=255)
    label_ar: str | None = Field(default=None, max_length=255)


class AssetColumnOrderIn(Schema):
    keys: list[str]


def _get_asset(request: Request, category: CategoryChoice, slug: str) -> Asset:
    return AssetContentService()._get_asset_or_404(slug, category, publisher_q=request.publisher_q())


def _require_manage_columns(request: Request) -> None:
    check_permission(request.user, PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS, raise_exception=True)
    check_permission(request.user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES, raise_exception=True)


_ASSET_NOT_FOUND = (
    NinjaErrorResponse[Literal["translation_not_found"]]
    | NinjaErrorResponse[Literal["tafsir_not_found"]]
    | NinjaErrorResponse[Literal["unsupported_content_category"]]
)


@router.get(
    "content/{category}/{slug}/columns/",
    response={200: list[AssetColumnOut], 404: _ASSET_NOT_FOUND},
)
def list_columns(request: Request, category: str, slug: str):
    """The asset's text columns, in file order."""
    resolved = _resolve(category, request, access="read")
    asset = _get_asset(request, resolved, slug)
    return asset.text_columns()


@router.post(
    "content/{category}/{slug}/columns/",
    response={
        201: AssetColumnOut,
        400: NinjaErrorResponse[Literal["column_key_invalid"]] | NinjaErrorResponse[Literal["column_key_taken"]],
        404: _ASSET_NOT_FOUND,
    },
)
def create_column(request: Request, category: str, slug: str, data: AssetColumnIn):
    """Add a column at the end; it appears in the next committed version."""
    resolved = _resolve(category, request, access="read")
    _require_manage_columns(request)
    asset = _get_asset(request, resolved, slug)
    column = AssetColumnService().create_column(asset, key=data.key, label_en=data.label_en, label_ar=data.label_ar)
    return 201, column


@router.put(
    "content/{category}/{slug}/columns/order/",
    response={
        200: list[AssetColumnOut],
        400: NinjaErrorResponse[Literal["column_order_mismatch"]],
        404: _ASSET_NOT_FOUND,
    },
)
def reorder_columns(request: Request, category: str, slug: str, data: AssetColumnOrderIn):
    """Set the column order. Reordering columns of a committed version makes the next version major."""
    resolved = _resolve(category, request, access="read")
    _require_manage_columns(request)
    asset = _get_asset(request, resolved, slug)
    return AssetColumnService().reorder_columns(asset, data.keys)


@router.patch(
    "content/{category}/{slug}/columns/{key}/",
    response={
        200: AssetColumnOut,
        400: NinjaErrorResponse[Literal["column_key_invalid"]]
        | NinjaErrorResponse[Literal["column_key_taken"]]
        | NinjaErrorResponse[Literal["column_committed"]],
        404: _ASSET_NOT_FOUND | NinjaErrorResponse[Literal["column_not_found"]],
    },
)
def update_column(request: Request, category: str, slug: str, key: str, data: AssetColumnPatchIn):
    """Change a column's labels, or its key while no committed version contains it."""
    resolved = _resolve(category, request, access="read")
    _require_manage_columns(request)
    asset = _get_asset(request, resolved, slug)
    service = AssetColumnService()
    column = service.get_column_or_404(asset, key)
    return service.update_column(column, key=data.key, label_en=data.label_en, label_ar=data.label_ar)


@router.delete(
    "content/{category}/{slug}/columns/{key}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["column_committed"]] | NinjaErrorResponse[Literal["column_last"]],
        404: _ASSET_NOT_FOUND | NinjaErrorResponse[Literal["column_not_found"]],
    },
)
def delete_column(request: Request, category: str, slug: str, key: str):
    """Delete a column no committed version contains, with its draft cells."""
    resolved = _resolve(category, request, access="read")
    _require_manage_columns(request)
    asset = _get_asset(request, resolved, slug)
    service = AssetColumnService()
    service.delete_column(service.get_column_or_404(asset, key))
    return 204, None
