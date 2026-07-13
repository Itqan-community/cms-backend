from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.content.services.font import FontService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.FONTS])


class FontVersionListOut(Schema):
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


class FontVersionCreateIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class FontVersionPutIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class FontVersionPatchIn(Schema):
    asset_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None


@router.get(
    "fonts/{font_slug}/versions/",
    response={
        200: list[FontVersionListOut],
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_FONT)])
@paginate
@searching(search_fields=["name", "summary"])
def list_font_versions(request: Request, font_slug: str):
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=font_slug, category=CategoryChoice.FONT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="font_not_found",
            message=_("Font with slug {slug} not found.").format(slug=font_slug),
            status_code=404,
        ) from exc
    return AssetVersion.objects.filter(asset=asset).order_by("-created_at")


@router.post(
    "fonts/{font_slug}/versions/",
    response={
        201: FontVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["font_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_FONT)])
def create_font_version(
    request: Request,
    font_slug: str,
    data: Form[FontVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = FontService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=font_slug, category=CategoryChoice.FONT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="font_not_found",
            message=_("Font with slug {slug} not found.").format(slug=font_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match font asset id {asset.id}",
            status_code=400,
        )

    version = service.create_font_version(
        font_slug,
        name=data.name,
        summary=data.summary,
        file=file,
        publisher_q=request.publisher_q(),
    )
    return 201, version


@router.put(
    "fonts/{font_slug}/versions/{version_id}/",
    response={
        200: FontVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["font_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_FONT)])
def update_font_version_put(
    request: Request,
    font_slug: str,
    version_id: int,
    data: Form[FontVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = FontService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=font_slug, category=CategoryChoice.FONT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="font_not_found",
            message=_("Font with slug {slug} not found.").format(slug=font_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match font asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_font_version(font_slug, version_id, fields=fields, publisher_q=request.publisher_q())


@router.patch(
    "fonts/{font_slug}/versions/{version_id}/",
    response={
        200: FontVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["font_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_FONT)])
def update_font_version_patch(
    request: Request,
    font_slug: str,
    version_id: int,
    data: Form[FontVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = FontService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=font_slug, category=CategoryChoice.FONT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="font_not_found",
            message=_("Font with slug {slug} not found.").format(slug=font_slug),
            status_code=404,
        ) from exc
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match font asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_font_version(font_slug, version_id, fields=fields, publisher_q=request.publisher_q())


@router.delete(
    "fonts/{font_slug}/versions/{version_id}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["font_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_FONT)])
def delete_font_version(request: Request, font_slug: str, version_id: int) -> tuple[int, None]:
    service = FontService()
    service.delete_font_version(font_slug, version_id, publisher_q=request.publisher_q())
    return 204, None
