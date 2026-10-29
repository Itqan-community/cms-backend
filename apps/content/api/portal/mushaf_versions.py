from typing import Literal

from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.api.portal.asset_content import SetPublishedIn, VersionTextIn, VersionTextOut
from apps.content.models import Asset, AssetLanguage, AssetVersion, CategoryChoice
from apps.content.services.asset_content import AssetContentService
from apps.content.services.mushaf import MushafService
from apps.content.version_text import VersionText
from apps.core.mixins.storage import absolute_file_url
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission, permission_class
from apps.core.permissions import PermissionChoice
from apps.package_manager.api.schemas import PackageStatusOut

router = ItqanRouter(tags=[NinjaTag.MUSHAFS])


class MushafVersionListOut(VersionTextOut, PackageStatusOut):
    id: int
    asset_id: int
    # The version consumers are served.
    is_published: bool
    # Publishing it goes back to an earlier version, which needs a reason.
    publishing_rolls_back: bool
    # Version number ("major.minor"), issued by the server; ``label_*`` is the version name.
    name: str
    summary: str
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_is_published(obj: AssetVersion) -> bool:
        return AssetLanguage.objects.filter(published_version_id=obj.id).exists()

    @staticmethod
    def resolve_publishing_rolls_back(obj: AssetVersion) -> bool:
        return obj.publishing_rolls_back()

    @staticmethod
    def resolve_file_url(obj: AssetVersion, context: dict) -> str | None:
        return absolute_file_url(context["request"], obj.file_url)


class MushafVersionCreateIn(VersionTextIn):
    asset_id: int
    # Starts the mushaf's number sequence; ignored once it has a version.
    version_number: str | None = Field(default=None, max_length=20)
    bump: Literal["minor", "major"] = "minor"
    # Make it the version consumers get right away (needs PORTAL_PUBLISH_CONTENT).
    publish: bool = False


# The version number (``name``) is fixed once issued, so updates can't change it.
class MushafVersionPutIn(VersionTextIn):
    asset_id: int


class MushafVersionPatchIn(Schema):
    asset_id: int | None = None
    label_en: str | None = Field(default=None, max_length=255)
    label_ar: str | None = Field(default=None, max_length=255)
    summary_en: str | None = None
    summary_ar: str | None = None


@router.get(
    "mushafs/{mushaf_slug}/versions/",
    response={
        200: list[MushafVersionListOut],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF)])
@paginate
@searching(search_fields=["name", "label_en", "label_ar", "summary_en", "summary_ar"])
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
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]]
        | NinjaErrorResponse[Literal["version_number_required"]]
        | NinjaErrorResponse[Literal["version_number_invalid"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
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
            message=_("Provided asset_id {asset_id} does not match mushaf asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    if data.publish:
        check_permission(
            request.user, PermissionChoice.PORTAL_PUBLISH_CONTENT, raise_exception=True, publisher=request.publisher
        )
    version = service.create_mushaf_version(
        mushaf_slug,
        text=VersionText.from_data(data),
        version_number=data.version_number,
        bump=data.bump,
        file=file,
        publish=data.publish,
        publisher_q=request.publisher_q(),
    )
    return 201, version


@router.put(
    "mushafs/{mushaf_slug}/versions/{version_id}/",
    response={
        200: MushafVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]] | NinjaErrorResponse[Literal["version_is_published"]],
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
            message=_("Provided asset_id {asset_id} does not match mushaf asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
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
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]] | NinjaErrorResponse[Literal["version_is_published"]],
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
            message=_("Provided asset_id {asset_id} does not match mushaf asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
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
        400: NinjaErrorResponse[Literal["version_is_published"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_MUSHAF)])
def delete_mushaf_version(request: Request, mushaf_slug: str, version_id: int) -> tuple[int, None]:
    service = MushafService()
    service.delete_mushaf_version(mushaf_slug, version_id, publisher_q=request.publisher_q())
    return 204, None


@router.post(
    "mushafs/{mushaf_slug}/versions/{version_id}/set-published/",
    response={
        200: MushafVersionListOut,
        400: NinjaErrorResponse[Literal["version_not_publishable"]]
        | NinjaErrorResponse[Literal["version_removed"]]
        | NinjaErrorResponse[Literal["rollback_reason_required"]],
        403: NinjaErrorResponse[Literal["permission_denied"]],
        404: NinjaErrorResponse[Literal["mushaf_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_PUBLISH_CONTENT)])
def set_published_mushaf_version(
    request: Request, mushaf_slug: str, version_id: int, data: SetPublishedIn | None = None
) -> AssetVersion:
    """Make a version the one consumers get. Going back to an earlier version requires ``reason``."""
    return AssetContentService().set_published_version(
        mushaf_slug,
        CategoryChoice.MUSHAF,
        version_id,
        reason=data.reason if data else "",
        publisher_q=request.publisher_q(),
    )
