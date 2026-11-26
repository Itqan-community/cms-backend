import json
from typing import Literal

from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from ninja import File, Form, Query, Schema, UploadedFile
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field, Json

from apps.content.api.portal.asset_content import VersionTextIn, VersionTextOut
from apps.content.api.portal.asset_review import change_counts, pending_review_count, with_change_counts
from apps.content.models import (
    DEFAULT_COLUMN_KEY,
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    CategoryChoice,
    ChangeTypeChoice,
    VersionStateChoice,
)
from apps.content.services.asset_columns import AssetColumnService
from apps.content.services.asset_content import (
    VersionDeleteBlockedReason,
    header_not_first_error,
    is_first_version,
    is_head_version,
    version_delete_blocked_reason,
)
from apps.content.services.asset_content_import import (
    PREVIEW_BYTES,
    AssetContentHeaderNotFirstError,
    AssetContentParseError,
    ColumnsPreview,
    preview_content_columns,
)
from apps.content.services.asset_language_access import (
    filter_versions_to_allowed,
    require_language,
    require_version_id,
)
from apps.content.services.asset_templates import UnitSpec, unit_spec_for, unit_spec_for_template
from apps.content.services.text_asset import TextAssetService
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

router = ItqanRouter(tags=[NinjaTag.TEXT_ASSETS])


class TextAssetVersionListOut(VersionTextOut, PackageStatusOut):
    id: int
    asset_id: int
    language: str
    # The latest commit (head) of its language — what the editor builds on.
    is_active: bool
    # The version consumers are served for its language.
    is_published: bool
    # Why the version cannot be deleted (the error a delete would return), or null.
    # Only the newest version of a language can be deleted; a published one only
    # while it is the language's first and only version.
    delete_blocked_reason: VersionDeleteBlockedReason | None
    # Publishing it goes back to an earlier version, which needs a reason.
    publishing_rolls_back: bool
    # Every change in it is approved, so it may be published.
    is_approved: bool
    # Units awaiting approval as of this version (0 when approved).
    pending_review_count: int
    # The first committed version of its language: there is nothing before it to
    # compare with, so its whole content is listed as added.
    is_first: bool
    # Version number ("major.minor"), issued by the server; never editable.
    name: str
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
    def resolve_is_active(obj: AssetVersion, context: dict) -> bool:
        return is_head_version(obj, context["request"].__dict__.setdefault("_committed_versions", {}))

    @staticmethod
    def resolve_is_published(obj: AssetVersion) -> bool:
        if obj.asset_language_id:
            return obj.asset_language.published_version_id == obj.id
        return AssetLanguage.objects.filter(published_version_id=obj.id).exists()

    @staticmethod
    def resolve_publishing_rolls_back(obj: AssetVersion) -> bool:
        return obj.publishing_rolls_back()

    @staticmethod
    def resolve_is_first(obj: AssetVersion, context: dict) -> bool:
        return is_first_version(obj, context["request"].__dict__.setdefault("_committed_versions", {}))

    @staticmethod
    def resolve_is_approved(obj: AssetVersion, context: dict) -> bool:
        return pending_review_count(obj, context) == 0

    @staticmethod
    def resolve_pending_review_count(obj: AssetVersion, context: dict) -> int:
        return pending_review_count(obj, context)

    @staticmethod
    def resolve_created_by(obj: AssetVersion) -> str | None:
        return obj.created_by.name if obj.created_by_id else None

    @staticmethod
    def resolve_review_comments_count(obj: AssetVersion) -> int:
        """Changes in this version a reviewer left a comment on."""
        return change_counts(obj)["commented_changes"]

    @staticmethod
    def resolve_change_counts(obj: AssetVersion) -> dict | None:
        counts = {change_type: change_counts(obj)[f"{change_type}_changes"] for change_type in ChangeTypeChoice.values}
        return counts if any(counts.values()) else None

    @staticmethod
    def resolve_delete_blocked_reason(obj: AssetVersion, context: dict) -> VersionDeleteBlockedReason | None:
        return version_delete_blocked_reason(obj, context["request"].__dict__.setdefault("_version_delete_reasons", {}))

    @staticmethod
    def resolve_file_url(obj: AssetVersion, context: dict) -> str | None:
        return absolute_file_url(context["request"], obj.file_url)


# A JSON object sent with a file upload: field key -> 0-based column index in
# the file's header row (null or left out: not in the file). Overrides the
# header alias matching; columns it does not name are ignored.
COLUMN_MAPPING_DESCRIPTION = (
    'JSON object mapping each field (e.g. "surah", "ayah", a text column key) to a 0-based column index of the '
    "file's header row. Overrides header name matching; unmapped columns are ignored."
)


def column_mapping_from_form(raw: str | None) -> dict[str, int | None] | None:
    """Decode the ``column_mapping`` form field; ``None`` when it was not sent."""
    if raw is None or not raw.strip():
        return None
    try:
        mapping = json.loads(raw)
    except ValueError:
        mapping = None
    if not isinstance(mapping, dict) or not all(
        isinstance(key, str) and (value is None or (isinstance(value, int) and not isinstance(value, bool)))
        for key, value in mapping.items()
    ):
        raise ItqanError(
            error_name="column_mapping_invalid",
            message=_("The column mapping must map each field to a column number."),
            status_code=400,
        )
    return mapping


class TextAssetVersionCreateIn(VersionTextIn):
    asset_id: int
    # Starts the language's number sequence; ignored once it has a version.
    version_number: str | None = Field(default=None, max_length=20)
    bump: Literal["minor", "major"] = "minor"
    language: str | None = None
    # Approve the uploaded changes on upload; needs the review permission.
    pre_approved: bool = False
    column_mapping: str | None = Field(default=None, description=COLUMN_MAPPING_DESCRIPTION)


# The version number (``name``) is fixed once issued, so updates can't change it.
class TextAssetVersionPutIn(VersionTextIn):
    asset_id: int
    column_mapping: str | None = Field(default=None, description=COLUMN_MAPPING_DESCRIPTION)


class TextAssetVersionPatchIn(Schema):
    asset_id: int | None = None
    label_en: str | None = Field(default=None, max_length=255)
    label_ar: str | None = Field(default=None, max_length=255)
    summary_en: str | None = None
    summary_ar: str | None = None
    column_mapping: str | None = Field(default=None, description=COLUMN_MAPPING_DESCRIPTION)


class ImportColumnFieldOut(Schema):
    key: str
    # "unit": where the row sits (surah, ayah, …); "text": one of the asset's text columns.
    kind: Literal["unit", "text"]
    label_en: str = ""
    label_ar: str = ""


class ImportColumnsPreviewOut(Schema):
    # 1-based row number of the header row in the file.
    header_row: int
    headers: list[str]
    # Up to 3 rows after the header, each cell cut to 120 characters.
    samples: list[list[str]]
    fields: list[ImportColumnFieldOut]
    # Mapping every field of any one list is enough to import.
    required: list[list[str]]
    # Fields matched by header name: field key -> 0-based column index.
    mapping: dict[str, int]
    # The auto-matched fields already cover a required list.
    complete: bool
    # Text rows between the header and the first data row (1-based); a strict
    # import rejects them, so the uploader should fix them first. Judged by the
    # sent `column_mapping`, else the name-matched columns when they cover every
    # required field; empty until the unit columns are known.
    attention_rows: list[int] = []


class ImportColumnIn(Schema):
    key: str = Field(..., max_length=64)
    label_en: str = Field(default="", max_length=255)
    label_ar: str = Field(default="", max_length=255)


class NewAssetImportColumnsIn(Schema):
    template: AssetTemplateChoice
    # The columns the create form will send (`columns`); just `text` when omitted.
    columns: Json[list[ImportColumnIn]] | None = None
    column_mapping: str | None = Field(default=None, description=COLUMN_MAPPING_DESCRIPTION)


def _import_columns_out(
    file: UploadedFile, spec: UnitSpec, columns: list, column_mapping: dict[str, int | None] | None = None
) -> dict:
    """Preview ``file``'s header row for ``columns`` (objects with key and labels).

    Only the first 64 KB are read (clients may send just that slice), so a large
    file is never parsed here.
    """
    prefix = file.read(PREVIEW_BYTES + 1)
    try:
        preview: ColumnsPreview = preview_content_columns(
            prefix[:PREVIEW_BYTES],
            spec,
            [column.key for column in columns],
            truncated=len(prefix) > PREVIEW_BYTES,
            column_mapping=column_mapping,
        )
    except AssetContentHeaderNotFirstError as exc:
        raise header_not_first_error() from exc
    except AssetContentParseError as exc:
        raise ItqanError(
            error_name="content_file_unparseable",
            message=_("The file's header row could not be read. Upload a UTF-8 CSV file with a header row."),
            status_code=400,
        ) from exc
    return {
        "header_row": preview.header_row,
        "headers": preview.headers,
        "samples": preview.samples,
        "fields": [{"key": key, "kind": "unit"} for key in preview.unit_fields]
        + [
            {"key": column.key, "kind": "text", "label_en": column.label_en or "", "label_ar": column.label_ar or ""}
            for column in columns
        ],
        "required": preview.required,
        "mapping": preview.mapping,
        "complete": preview.complete,
        "attention_rows": preview.attention_rows,
    }


@router.get(
    "text-assets/{text_asset_slug}/versions/",
    response={
        200: list[TextAssetVersionListOut],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TEXT_ASSET)])
@paginate
@searching(search_fields=["name", "label_en", "label_ar", "summary_en", "summary_ar"])
def list_text_asset_versions(request: Request, text_asset_slug: str, language: str | None = None):
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    versions = AssetVersion.objects.filter(asset=asset, state=VersionStateChoice.PUBLISHED).select_related(
        "created_by", "asset_language__published_version", "asset"
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
    return with_change_counts(versions).order_by("-created_at")


@router.post(
    "text-assets/{text_asset_slug}/import-columns/",
    response={
        200: ImportColumnsPreviewOut,
        400: NinjaErrorResponse[Literal["content_file_unparseable"]],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_TEXT_ASSET)])
def preview_import_columns(
    request: Request,
    text_asset_slug: str,
    file: UploadedFile = File(...),
    column_mapping: str | None = Form(None, description=COLUMN_MAPPING_DESCRIPTION),
):
    """Read a content file's header row, auto-match it to the asset's fields and
    list what still needs a column, so the uploader can map the rest."""
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    return _import_columns_out(
        file, unit_spec_for(asset), asset.text_columns(), column_mapping_from_form(column_mapping)
    )


@router.post(
    "content/text-assets/import-columns/",
    response={
        200: ImportColumnsPreviewOut,
        400: NinjaErrorResponse[Literal["content_file_unparseable"]]
        | NinjaErrorResponse[Literal["column_key_invalid"]]
        | NinjaErrorResponse[Literal["column_key_taken"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_TEXT_ASSET)])
def preview_new_asset_import_columns(
    request: Request, data: Form[NewAssetImportColumnsIn], file: UploadedFile = File(...)
):
    """The same preview for the create form, before the asset exists: the fields
    come from the chosen template and the columns the form will create."""
    columns = data.columns or [ImportColumnIn(key=DEFAULT_COLUMN_KEY)]
    AssetColumnService.validate_new_keys([column.key for column in columns])
    return _import_columns_out(
        file, unit_spec_for_template(data.template), columns, column_mapping_from_form(data.column_mapping)
    )


@router.post(
    "text-assets/{text_asset_slug}/versions/",
    response={
        201: TextAssetVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]]
        | NinjaErrorResponse[Literal["content_file_unparseable"]]
        | NinjaErrorResponse[Literal["content_file_missing_columns"]]
        | NinjaErrorResponse[Literal["content_file_invalid_rows"]]
        | NinjaErrorResponse[Literal["column_mapping_invalid"]]
        | NinjaErrorResponse[Literal["column_mapping_incomplete"]]
        | NinjaErrorResponse[Literal["version_number_required"]]
        | NinjaErrorResponse[Literal["version_number_invalid"]],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]],
    },
)
# Uploading a version changes the asset's text, so it needs the content permission.
@permission_required([permission_class(PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT)])
def create_text_asset_version(
    request: Request,
    text_asset_slug: str,
    data: Form[TextAssetVersionCreateIn],
    file: UploadedFile = File(...),
) -> tuple[int, AssetVersion]:
    service = TextAssetService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match text asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    # language is optional; omitting it targets the asset's source language.
    require_language(request.user, asset, data.language or asset.language)
    if data.pre_approved:
        check_permission(
            request.user, PermissionChoice.PORTAL_REVIEW_CONTENT, raise_exception=True, publisher=request.publisher
        )
    version = service.create_text_asset_version(
        text_asset_slug,
        text=VersionText.from_data(data),
        version_number=data.version_number,
        bump=data.bump,
        file=file,
        language=data.language,
        created_by_id=request.user.id,
        approved_by=request.user if data.pre_approved else None,
        publisher_q=request.publisher_q(),
        column_mapping=column_mapping_from_form(data.column_mapping),
    )
    return 201, version


@router.put(
    "text-assets/{text_asset_slug}/versions/{version_id}/",
    response={
        200: TextAssetVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]]
        | NinjaErrorResponse[Literal["version_is_published"]]
        | NinjaErrorResponse[Literal["version_not_latest"]]
        | NinjaErrorResponse[Literal["content_file_unparseable"]]
        | NinjaErrorResponse[Literal["content_file_missing_columns"]]
        | NinjaErrorResponse[Literal["content_file_invalid_rows"]]
        | NinjaErrorResponse[Literal["column_mapping_invalid"]]
        | NinjaErrorResponse[Literal["column_mapping_incomplete"]],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)])
def update_text_asset_version_put(
    request: Request,
    text_asset_slug: str,
    version_id: int,
    data: Form[TextAssetVersionPutIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TextAssetService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    if data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match text asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    fields = data.model_dump()
    fields.pop("asset_id", None)
    column_mapping = column_mapping_from_form(fields.pop("column_mapping", None))
    if file:
        # Replacing the file changes the text; renaming or re-describing does not.
        check_permission(
            request.user,
            PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT,
            raise_exception=True,
            publisher=request.publisher,
        )
        fields["file_url"] = file

    require_version_id(request.user, asset, version_id)
    return service.update_text_asset_version(
        text_asset_slug,
        version_id,
        fields=fields,
        publisher_q=request.publisher_q(),
        column_mapping=column_mapping if file else None,
    )


@router.patch(
    "text-assets/{text_asset_slug}/versions/{version_id}/",
    response={
        200: TextAssetVersionListOut,
        400: NinjaErrorResponse[Literal["asset_id_mismatch"]]
        | NinjaErrorResponse[Literal["version_is_published"]]
        | NinjaErrorResponse[Literal["version_not_latest"]]
        | NinjaErrorResponse[Literal["content_file_unparseable"]]
        | NinjaErrorResponse[Literal["content_file_missing_columns"]]
        | NinjaErrorResponse[Literal["content_file_invalid_rows"]]
        | NinjaErrorResponse[Literal["column_mapping_invalid"]]
        | NinjaErrorResponse[Literal["column_mapping_incomplete"]],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_TEXT_ASSET)])
def update_text_asset_version_patch(
    request: Request,
    text_asset_slug: str,
    version_id: int,
    data: Form[TextAssetVersionPatchIn],
    file: UploadedFile | None = File(None),
) -> AssetVersion:
    service = TextAssetService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    if data.asset_id is not None and data.asset_id != asset.id:
        raise ItqanError(
            error_name="asset_id_mismatch",
            message=_("Provided asset_id {asset_id} does not match text asset id {expected_id}.").format(
                asset_id=data.asset_id, expected_id=asset.id
            ),
            status_code=400,
        )

    fields = data.model_dump(exclude_unset=True)
    fields.pop("asset_id", None)
    column_mapping = column_mapping_from_form(fields.pop("column_mapping", None))
    if file:
        # Replacing the file changes the text; renaming or re-describing does not.
        check_permission(
            request.user,
            PermissionChoice.PORTAL_EDIT_TEXT_ASSET_CONTENT,
            raise_exception=True,
            publisher=request.publisher,
        )
        fields["file_url"] = file

    require_version_id(request.user, asset, version_id)
    return service.update_text_asset_version(
        text_asset_slug,
        version_id,
        fields=fields,
        publisher_q=request.publisher_q(),
        column_mapping=column_mapping if file else None,
    )


@router.delete(
    "text-assets/{text_asset_slug}/versions/{version_id}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["version_is_published"]] | NinjaErrorResponse[Literal["version_not_latest"]],
        409: NinjaErrorResponse[Literal["unpublish_not_confirmed"]],
        404: NinjaErrorResponse[Literal["text_asset_not_found"]] | NinjaErrorResponse[Literal["version_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_TEXT_ASSET)])
def delete_text_asset_version(
    request: Request, text_asset_slug: str, version_id: int, confirm_unpublish: bool = Query(False)
) -> tuple[int, None]:
    service = TextAssetService()
    try:
        asset = Asset.objects.filter(request.publisher_q()).get(slug=text_asset_slug, category=CategoryChoice.TEXT)
    except Asset.DoesNotExist as exc:
        raise ItqanError(
            error_name="text_asset_not_found",
            message=_("Text asset with slug {slug} not found.").format(slug=text_asset_slug),
            status_code=404,
        ) from exc
    require_version_id(request.user, asset, version_id)
    service.delete_text_asset_version(
        text_asset_slug, version_id, publisher_q=request.publisher_q(), confirm_unpublish=confirm_unpublish
    )
    return 204, None
