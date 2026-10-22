"""Gallery: what a text asset's download looks like before downloading it."""

from typing import Literal

from django.shortcuts import get_object_or_404
from ninja import Schema

from apps.content.models import Asset
from apps.content.services.asset_columns import FileStructureService
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.ASSETS])


class FileStructureColumnOut(Schema):
    key: str
    label_en: str
    label_ar: str


class AssetFileStructureOut(Schema):
    format: Literal["csv"] = "csv"
    template: str
    header: list[str]
    columns: list[FileStructureColumnOut]
    rows: list[list[str]]


@router.get(
    "assets/{id}/file-structure/",
    response={200: AssetFileStructureOut, 404: NinjaErrorResponse[Literal["file_structure_unavailable"]]},
    auth=None,
)
def asset_file_structure(request: Request, id: int, language: str | None = None):
    """The download's format, its columns (keys and labels) and its first rows, for
    one language (default: the source). Translations and tafsirs only."""
    asset = get_object_or_404(Asset, request.publisher_q("publisher"), restricted_for_tenant=False, id=id)
    preview = FileStructureService().preview(asset, language)
    return {
        "template": preview.structure.template,
        "header": preview.structure.header,
        "columns": preview.structure.columns,
        "rows": preview.rows,
    }
