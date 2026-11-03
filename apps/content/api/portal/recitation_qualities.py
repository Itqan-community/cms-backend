import logging
from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from pydantic import AwareDatetime

from apps.content.models import Asset, CategoryChoice
from apps.content.services.recitation_quality import RecitationQualityService
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


class QualityOut(Schema):
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


class QualityCreateIn(Schema):
    name_ar: str = Field(default="", max_length=255)
    name_en: str = Field(default="", max_length=255)


class QualityPatchIn(Schema):
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
    "recitations/{recitation_slug}/qualities/",
    response={
        200: list[QualityOut],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_RECITATION)])
def list_qualities(request: Request, recitation_slug: str):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationQualityService()
    return service.list_qualities(asset.id, annotate_tracks_count=True)


@router.post(
    "recitations/{recitation_slug}/qualities/",
    response={
        201: QualityOut,
        400: NinjaErrorResponse[Literal["quality_name_required"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_RECITATION)])
def create_quality(request: Request, recitation_slug: str, data: QualityCreateIn):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationQualityService()
    quality = service.create_quality(asset_id=asset.id, name_ar=data.name_ar, name_en=data.name_en)
    logger.info(
        f"Recitation quality created via portal [quality_id={quality.id}, asset_id={asset.id}, user_id={request.user.id}]"
    )
    return 201, quality


@router.patch(
    "recitations/{recitation_slug}/qualities/{quality_slug}/",
    response={
        200: QualityOut,
        400: NinjaErrorResponse[
            Literal[
                "quality_name_required",
                "cannot_hide_default_quality",
                "cannot_unset_default_quality",
                "cannot_set_hidden_quality_as_default",
            ]
        ],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]] | NinjaErrorResponse[Literal["quality_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_RECITATION)])
def update_quality(request: Request, recitation_slug: str, quality_slug: str, data: QualityPatchIn):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationQualityService()
    quality = service.update_quality(
        asset_id=asset.id,
        quality_slug=quality_slug,
        fields=data.model_dump(exclude_unset=True),
    )
    logger.info(
        f"Recitation quality updated via portal [quality_id={quality.id}, asset_id={asset.id}, user_id={request.user.id}]"
    )
    return quality


@router.delete(
    "recitations/{recitation_slug}/qualities/{quality_slug}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["cannot_delete_default_quality"]],
        401: NinjaErrorResponse[Literal["authentication_error"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["recitation_not_found"]] | NinjaErrorResponse[Literal["quality_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_RECITATION)])
def delete_quality(request: Request, recitation_slug: str, quality_slug: str):
    asset = _get_recitation_or_404(request, recitation_slug)
    service = RecitationQualityService()
    service.delete_quality(asset_id=asset.id, quality_slug=quality_slug)
    logger.info(
        f"Recitation quality deleted via portal [asset_id={asset.id}, slug={quality_slug}, user_id={request.user.id}]"
    )
    return 204, None
