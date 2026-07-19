from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.content.services.mushaf import MushafService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.MUSHAFS])


class MushafVersionListOut(Schema):
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


class MushafVersionCreateIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class MushafVersionPutIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class MushafVersionPatchIn(Schema):
    asset_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None


@router.get(
    "mushafs/{mushaf_slug}/versions/",
    response={
        200: list[MushafVersionListOut],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF)])
@paginate
@searching(search_fields=["name", "summary"])
def list_mushaf_versions(request: Request, mushaf_slug: str):
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_not_found",
            message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
            status_code=404,
        ) from exc
    return AssetVersion.objects.filter(asset=asset).order_by("-created_at")


@router.post(
    "mushafs/{mushaf_slug}/versions/",
    response={
        201: MushafVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_MUSHAF)])
def create_mushaf_version(
    request: Request,
    mushaf_slug: str,
    data: Form[MushafVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = MushafService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_not_found",
            message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match mushaf asset id {asset.id}",
            status_code=400,
        )

    version = service.create_mushaf_version(
        mushaf_slug,
        name=data.name,
        summary=data.summary,
        file=file,
        publisher_q=request.publisher_q(),
    )
    return 201, version


@router.put(
    "mushafs/{mushaf_slug}/versions/{version_id}/",
    response={
        200: MushafVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF)])
def update_mushaf_version_put(
    request: Request,
    mushaf_slug: str,
    version_id: int,
    data: Form[MushafVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = MushafService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_not_found",
            message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match mushaf asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_mushaf_version(mushaf_slug, version_id, fields=fields, publisher_q=request.publisher_q())


@router.patch(
    "mushafs/{mushaf_slug}/versions/{version_id}/",
    response={
        200: MushafVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF)])
def update_mushaf_version_patch(
    request: Request,
    mushaf_slug: str,
    version_id: int,
    data: Form[MushafVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = MushafService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=mushaf_slug, category=CategoryChoice.MUSHAF)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_not_found",
            message=_("Mushaf with slug {slug} not found.").format(slug=mushaf_slug),
            status_code=404,
        ) from exc
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match mushaf asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_mushaf_version(mushaf_slug, version_id, fields=fields, publisher_q=request.publisher_q())


@router.delete(
    "mushafs/{mushaf_slug}/versions/{version_id}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["mushaf_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_MUSHAF)])
def delete_mushaf_version(request: Request, mushaf_slug: str, version_id: int) -> tuple[int, None]:
    service = MushafService()
    service.delete_mushaf_version(mushaf_slug, version_id, publisher_q=request.publisher_q())
    return 204, None
