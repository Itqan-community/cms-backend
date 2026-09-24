from typing import Literal

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import Asset, AssetVersion, CategoryChoice, StatusChoice, VersionStateChoice
from apps.content.services.asset_language_access import (
    filter_versions_to_allowed,
    require_language,
    require_version_id,
)
from apps.content.services.translation import TranslationService
from apps.core.mixins.storage import absolute_file_url
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission, permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class TranslationVersionListOut(Schema):
    id: int
    asset_id: int
    language: str
    is_active: bool
    name: str
    summary: str
    created_by: str | None
    change_counts: dict | None
    review_comments_count: int = 0
    file_url: str | None = None
    size_bytes: int
    created_at: AwareDatetime

    @staticmethod
    def resolve_language(obj: AssetVersion) -> str:
        return obj.asset_language.language if obj.asset_language_id else obj.asset.language

    @staticmethod
    def resolve_is_active(obj: AssetVersion) -> bool:
        language = obj.asset_language.language if obj.asset_language_id else obj.asset.language
        latest = obj.asset.get_latest_version(language)
        return latest is not None and latest.id == obj.id

    @staticmethod
    def resolve_created_by(obj: AssetVersion) -> str | None:
        return obj.created_by.name if obj.created_by_id else None

    @staticmethod
    def resolve_review_comments_count(obj: AssetVersion) -> int:
        """Changes in this version a reviewer left a comment on."""
        return sum(1 for change in obj.changes.all() if getattr(change, "review", None) and change.review.comment)

    @staticmethod
    def resolve_change_counts(obj: AssetVersion) -> dict | None:
        rows = list(obj.changes.all())
        if not rows:
            return None
        counts = {"added": 0, "modified": 0, "removed": 0}
        for change in rows:
            counts[change.change_type] = counts.get(change.change_type, 0) + 1
        return counts

    @staticmethod
    def resolve_file_url(obj: AssetVersion, context: dict) -> str | None:
        return absolute_file_url(context["request"], obj.file_url)


class TranslationVersionCreateIn(Schema):
    asset_id: int
    name: str = Field(..., max_length=255)
    summary: str = ""
    language: str | None = None


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
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TRANSLATION)])
@paginate
@searching(search_fields=["name", "summary"])
def list_translation_versions(request: Request, translation_slug: str, language: str | None = None):
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc
    versions = (
        AssetVersion.objects.filter(asset=asset, state=VersionStateChoice.PUBLISHED)
        .select_related("created_by", "asset_language", "asset")
        .prefetch_related("changes__review")
    )
    if language:
        require_language(request.user, asset, language)
        # Legacy versions have no asset_language and belong to the source
        # language; include them when the source language is requested.
        language_q = Q(asset_language__language=language)
        if language == asset.language:
            language_q |= Q(asset_language__isnull=True)
        versions = versions.filter(language_q)
    else:
        versions = filter_versions_to_allowed(request.user, asset, versions)
    return versions.order_by("-created_at")


@router.post(
    "translations/{translation_slug}/versions/",
    response={
        201: TranslationVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]],
    },
)
# Uploading a version changes the asset's text, so it needs the content permission.
@permission_required([permission_class(PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT)])
def create_translation_version(
    request: Request,
    translation_slug: str,
    data: Form[TranslationVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = TranslationService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match translation asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    # language is optional; omitting it targets the asset's source language.
    require_language(request.user, asset, data.language or asset.language)
    version = service.create_translation_version(
        translation_slug,
        name=data.name,
        summary=data.summary,
        file=file,
        language=data.language,
        publisher_q=request.publisher_q(),
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
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TRANSLATION)])
def update_translation_version_put(
    request: Request,
    translation_slug: str,
    version_id: int,
    data: Form[TranslationVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TranslationService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match translation asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    if file:
        # Replacing the file changes the text; renaming or re-describing does not.
        check_permission(request.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT, raise_exception=True)
        fields["file_url"] = file

    require_version_id(request.user, asset, version_id)
    return service.update_translation_version(
        translation_slug, version_id, fields=fields, publisher_q=request.publisher_q()
    )


@router.patch(
    "translations/{translation_slug}/versions/{version_id}/",
    response={
        200: TranslationVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TRANSLATION)])
def update_translation_version_patch(
    request: Request,
    translation_slug: str,
    version_id: int,
    data: Form[TranslationVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TranslationService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match translation asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    if file:
        # Replacing the file changes the text; renaming or re-describing does not.
        check_permission(request.user, PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT, raise_exception=True)
        fields["file_url"] = file

    require_version_id(request.user, asset, version_id)
    return service.update_translation_version(
        translation_slug, version_id, fields=fields, publisher_q=request.publisher_q()
    )


@router.delete(
    "translations/{translation_slug}/versions/{version_id}/",
    response={
        204: None,
        404: NinjaErrorResponse[Literal["translation_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_TRANSLATION)])
def delete_translation_version(request: Request, translation_slug: str, version_id: int) -> tuple[int, None]:
    service = TranslationService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(
            slug=translation_slug, category=CategoryChoice.TRANSLATION, status=StatusChoice.READY
        )
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="translation_not_found",
            message=_("Translation with slug {slug} not found.").format(slug=translation_slug),
            status_code=404,
        ) from exc
    require_version_id(request.user, asset, version_id)
    service.delete_translation_version(translation_slug, version_id, publisher_q=request.publisher_q())
    return 204, None
