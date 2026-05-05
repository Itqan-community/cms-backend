from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.content.services.tafsir import TafsirService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TAFSIRS])


class TafsirVersionListOut(Schema):
    id: int
    asset_id: int
    name: str
    summary: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_file_url(obj: AssetVersion) -> str | None:
        if obj.file_url:
            return obj.file_url.url
        return None


class TafsirVersionCreateIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class TafsirVersionPutIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class TafsirVersionPatchIn(Schema):
    asset_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None


@router.get(
    "tafsirs/{tafsir_slug}/versions/",
    response={
        200: list[TafsirVersionListOut],
        404: NinjaErrorResponse[Literal["tafsir_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TAFSIR)])
@paginate
@searching(search_fields=["name", "summary"])
def list_tafsir_versions(request: Request, tafsir_slug: str):
    try:
        asset = Asset.objects.get(slug=tafsir_slug, category=CategoryChoice.TAFSIR)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="tafsir_not_found",
            message=_("Tafsir with slug {slug} not found.").format(slug=tafsir_slug),
            status_code=404,
        ) from exc
    return AssetVersion.objects.filter(asset=asset).order_by("-created_at")


@router.post(
    "tafsirs/{tafsir_slug}/versions/",
    response={
        201: TafsirVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["tafsir_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_TAFSIR)])
def create_tafsir_version(
    request: Request,
    tafsir_slug: str,
    data: Form[TafsirVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = TafsirService()
    try:
        asset = Asset.objects.get(slug=tafsir_slug, category=CategoryChoice.TAFSIR)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="tafsir_not_found",
            message=_("Tafsir with slug {slug} not found.").format(slug=tafsir_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match tafsir asset id {asset.id}",
            status_code=400,
        )

    version = service.create_tafsir_version(
        tafsir_slug,
        name=data.name,
        summary=data.summary,
        file=file,
    )
    return 201, version


@router.put(
    "tafsirs/{tafsir_slug}/versions/{version_id}/",
    response={
        200: TafsirVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["tafsir_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TAFSIR)])
def update_tafsir_version_put(
    request: Request,
    tafsir_slug: str,
    version_id: int,
    data: Form[TafsirVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TafsirService()
    try:
        asset = Asset.objects.get(slug=tafsir_slug, category=CategoryChoice.TAFSIR)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="tafsir_not_found",
            message=_("Tafsir with slug {slug} not found.").format(slug=tafsir_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match tafsir asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_tafsir_version(tafsir_slug, version_id, fields=fields)


@router.patch(
    "tafsirs/{tafsir_slug}/versions/{version_id}/",
    response={
        200: TafsirVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["tafsir_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TAFSIR)])
def update_tafsir_version_patch(
    request: Request,
    tafsir_slug: str,
    version_id: int,
    data: Form[TafsirVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TafsirService()
    try:
        asset = Asset.objects.get(slug=tafsir_slug, category=CategoryChoice.TAFSIR)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="tafsir_not_found",
            message=_("Tafsir with slug {slug} not found.").format(slug=tafsir_slug),
            status_code=404,
        ) from exc
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match tafsir asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_tafsir_version(tafsir_slug, version_id, fields=fields)


@router.delete(
    "tafsirs/{tafsir_slug}/versions/{version_id}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["tafsir_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_TAFSIR)])
def delete_tafsir_version(request: Request, tafsir_slug: str, version_id: int) -> tuple[int, None]:
    service = TafsirService()
    service.delete_tafsir_version(tafsir_slug, version_id)
    return 204, None
