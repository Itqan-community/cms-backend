from typing import Literal

from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import AssetVersion
from apps.content.services.translation import TranslationService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class TranslationVersionListOut(Schema):
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


class TranslationVersionCreateIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class TranslationVersionPutIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""


class TranslationVersionPatchIn(Schema):
    asset_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None


@router.get(
    "translations/{translation_slug}/versions/",
    response={
        200: list[TranslationVersionListOut],
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.READ_PORTAL_TRANSLATION)])
@paginate
@searching(search_fields=["name", "summary"])
def list_translation_versions(request: Request, translation_slug: str):
    service = TranslationService()
    return service.get_translation_versions(translation_slug)


@router.post(
    "translations/{translation_slug}/versions/",
    response={
        201: TranslationVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.CREATE_PORTAL_TRANSLATION)])
def create_translation_version(
    request: Request,
    translation_slug: str,
    data: Form[TranslationVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = TranslationService()
    asset = service.get_translation(translation_slug)
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match translation asset id {asset.id}",
            status_code=400,
        )

    version = service.create_translation_version(
        translation_slug,
        name=data.name,
        summary=data.summary,
        file=file,
    )
    return 201, version


@router.put(
    "translations/{translation_slug}/versions/{version_id}/",
    response={
        200: TranslationVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.UPDATE_PORTAL_TRANSLATION)])
def update_translation_version_put(
    request: Request,
    translation_slug: str,
    version_id: int,
    data: Form[TranslationVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TranslationService()
    asset = service.get_translation(translation_slug)
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match translation asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_translation_version(translation_slug, version_id, fields=fields)


@router.patch(
    "translations/{translation_slug}/versions/{version_id}/",
    response={
        200: TranslationVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.UPDATE_PORTAL_TRANSLATION)])
def update_translation_version_patch(
    request: Request,
    translation_slug: str,
    version_id: int,
    data: Form[TranslationVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TranslationService()
    asset = service.get_translation(translation_slug)
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=f"Provided asset_id {data.asset_id} does not match translation asset id {asset.id}",
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    if file:
        fields["file_url"] = file

    return service.update_translation_version(translation_slug, version_id, fields=fields)


@router.delete(
    "translations/{translation_slug}/versions/{version_id}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["translation_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.DELETE_PORTAL_TRANSLATION)])
def delete_translation_version(request: Request, translation_slug: str, version_id: int) -> tuple[int, None]:
    service = TranslationService()
    service.delete_translation_version(translation_slug, version_id)
    return 204, None
