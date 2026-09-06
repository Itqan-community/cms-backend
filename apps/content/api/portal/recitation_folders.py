import logging
from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from pydantic import AwareDatetime

from apps.content.models import Asset, CategoryChoice
from apps.content.services.recitation_folder import RecitationFolderService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])
logger = logging.getLogger(__name__)


# --- Schemas ---


class FolderOut(Schema):
    id: int
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    slug: str
    is_default: bool
    is_visible: bool
    tracks_count: int = 0
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @staticmethod
    def resolve_tracks_count(obj) -> int:
        return getattr(obj, "tracks_count", 0)


class FolderCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)


class FolderPatchIn(Schema):
    name_ar: str | None = Field(default=None, max_length=255)
    name_en: str | None = Field(default=None, max_length=255)
    is_visible: bool | None = None
    is_default: bool | None = None


# --- Helpers ---


def _get_recitation_or_404(request: Request, recitation_slug: str) -> Asset:
    """Resolve a recitation the caller's publisher is allowed to see."""
    try:
        return Asset.objects.filter(request.publisher_q()).get(slug=recitation_slug, category=CategoryChoice.RECITATION)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="recitation_not_found",
            message=_("Recitation with slug {slug} not found.").format(slug=recitation_slug),
            status_code=404,
        ) from exc


# --- Endpoints ---


@router.get(
    "recitations/{recitation_slug}/folders/",
    response={
        200: list[FolderOut],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
def list_folders(request: Request, recitation_slug: str):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationFolderService()
    return service.list_folders(asset.id, annotate_tracks_count=True)


@router.post(
    "recitations/{recitation_slug}/folders/",
    response={
        201: FolderOut,
        400: NinjaErrorResponse[Literal["folder_name_required"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)])
def create_folder(request: Request, recitation_slug: str, data: FolderCreateIn):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationFolderService()
    folder = service.create_folder(asset_id=asset.id, name_ar=data.name_ar, name_en=data.name_en)
    logger.info(
        f"Recitation folder created via portal [folder_id={folder.id}, asset_id={asset.id}, user_id={request.user.id}]"
    )
    return 201, folder


@router.patch(
    "recitations/{recitation_slug}/folders/{folder_slug}/",
    response={
        200: FolderOut,
        400: NinjaErrorResponse[
            Literal[
                "folder_name_required",
                "cannot_hide_default_folder",
                "cannot_unset_default_folder",
                "cannot_set_hidden_folder_as_default",
            ]
        ],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]] | NinjaErrorResponse[Literal["folder_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)])
def update_folder(request: Request, recitation_slug: str, folder_slug: str, data: FolderPatchIn):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationFolderService()
    folder = service.update_folder(
        asset_id=asset.id,
        folder_slug=folder_slug,
        fields=data.model_dump(exclude_unset=True),
    )
    logger.info(
        f"Recitation folder updated via portal [folder_id={folder.id}, asset_id={asset.id}, user_id={request.user.id}]"
    )
    return folder


@router.delete(
    "recitations/{recitation_slug}/folders/{folder_slug}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["cannot_delete_default_folder"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]] | NinjaErrorResponse[Literal["folder_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_RECITATION)])
def delete_folder(request: Request, recitation_slug: str, folder_slug: str):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationFolderService()
    service.delete_folder(asset_id=asset.id, folder_slug=folder_slug)
    logger.info(
        f"Recitation folder deleted via portal [asset_id={asset.id}, slug={folder_slug}, user_id={request.user.id}]"
    )
    return 204, None
