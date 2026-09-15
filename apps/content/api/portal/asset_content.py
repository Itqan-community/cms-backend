"""Portal endpoints for per-ayah editing of text assets (translations & tafsirs).

One router serves both categories, keyed by a ``{category}`` path segment, so
the draft / entries / publish / discard flow lives in a single place.
"""

from typing import Literal

from django.http import HttpResponse, HttpResponseRedirect
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy as _
from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import AssetVersion, AssetVersionEntry, CategoryChoice
from apps.content.services.asset_content import AssetContentService
from apps.content.services.asset_language_access import require_language, require_version_language
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])

# Path segment -> (category, read perm, write perm).
_CATEGORY_CONFIG = {
    "translations": (
        CategoryChoice.TRANSLATION,
        PermissionChoice.PORTAL_READ_TRANSLATION,
        PermissionChoice.PORTAL_UPDATE_TRANSLATION,
    ),
    "tafsirs": (
        CategoryChoice.TAFSIR,
        PermissionChoice.PORTAL_READ_TAFSIR,
        PermissionChoice.PORTAL_UPDATE_TAFSIR,
    ),
}


def _resolve(category: str, request: Request, *, write: bool) -> CategoryChoice:
    """Resolve the category path segment and enforce the matching permission.

    One endpoint serves both translations and tafsirs, so the correct
    per-category permission is enforced here rather than by a static decorator.
    """
    config = _CATEGORY_CONFIG.get(category)
    if config is None:
        raise ItqanError(
            error_name="unsupported_content_category",
            message=_("Unsupported content category: {category}").format(category=category),
            status_code=404,
        )
    resolved, read_perm, write_perm = config
    check_permission(request.user, write_perm if write else read_perm, raise_exception=True)
    return resolved


def _resolve_for_version(category: str, request: Request, slug: str, version_id: int, *, write: bool) -> CategoryChoice:
    """``_resolve`` plus the per-language gate for a version-scoped operation.

    These endpoints address content by version id rather than by language, so the
    filtered language list does not constrain them on its own: without this check
    an unassigned language's content would be reachable by id alone. Reads are
    gated as well as writes, for that reason.
    """
    resolved = _resolve(category, request, write=write)
    version = AssetContentService().get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())
    require_version_language(request.user, version.asset, version)
    return resolved


class DraftVersionOut(Schema):
    id: int
    asset_id: int
    language: str
    name: str
    summary: str
    state: str
    entries_count: int
    has_changes: bool
    created_at: AwareDatetime

    @staticmethod
    def resolve_language(obj: AssetVersion) -> str:
        return obj.asset_language.language if obj.asset_language_id else obj.asset.language

    @staticmethod
    def resolve_entries_count(obj: AssetVersion) -> int:
        return obj.entries.count()

    @staticmethod
    def resolve_has_changes(obj: AssetVersion) -> bool:
        return obj.content_edited


class EntryOut(Schema):
    id: int
    ayah_id: int
    sura: int
    aya: int
    surah_name: str
    uthmani: str
    text: str
    source_text: str | None = None
    order: int

    @staticmethod
    def resolve_sura(obj: AssetVersionEntry) -> int:
        return obj.ayah.sura_id

    @staticmethod
    def resolve_aya(obj: AssetVersionEntry) -> int:
        return obj.ayah.number_in_sura

    @staticmethod
    def resolve_surah_name(obj: AssetVersionEntry) -> str:
        return obj.ayah.sura.name

    @staticmethod
    def resolve_uthmani(obj: AssetVersionEntry) -> str:
        return obj.ayah.text


class EntryPatchRow(Schema):
    ayah_id: int
    text: str = ""


class EntriesPatchIn(Schema):
    rows: list[EntryPatchRow] = Field(default_factory=list)


class PublishIn(Schema):
    message: str


class ChangeOut(Schema):
    ayah_id: int
    sura: int
    aya: int
    surah_name: str
    change_type: str
    old_text: str
    new_text: str


class DraftIn(Schema):
    language: str


@router.post(
    "content/{category}/{slug}/draft/",
    response={
        200: DraftVersionOut,
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["language_not_available"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def get_or_create_draft(request: Request, category: str, slug: str, data: DraftIn) -> AssetVersion:
    resolved = _resolve(category, request, write=True)
    service = AssetContentService()
    asset = service._get_asset_or_404(slug, resolved, publisher_q=request.publisher_q())
    require_language(request.user, asset, data.language)
    return service.get_or_create_draft(
        slug,
        resolved,
        language=data.language,
        created_by_id=getattr(request.user, "id", None),
        publisher_q=request.publisher_q(),
    )


@router.get(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: list[EntryOut],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
@paginate
def list_entries(request: Request, category: str, slug: str, version_id: int):
    resolved = _resolve_for_version(category, request, slug, version_id, write=False)
    service = AssetContentService()
    return service.get_entries(slug, resolved, version_id, publisher_q=request.publisher_q())


@router.patch(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: list[EntryOut],
        400: NinjaErrorResponse[Literal["version_not_editable"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def patch_entries(
    request: Request, category: str, slug: str, version_id: int, data: EntriesPatchIn
) -> list[AssetVersionEntry]:
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    rows = [row.model_dump() for row in data.rows]
    return service.upsert_entries(slug, resolved, version_id, rows, publisher_q=request.publisher_q())


@router.get(
    "content/{category}/{slug}/versions/{version_id}/diff/",
    response={
        200: list[ChangeOut],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
@paginate
def version_diff(request: Request, category: str, slug: str, version_id: int):
    resolved = _resolve_for_version(category, request, slug, version_id, write=False)
    service = AssetContentService()
    return service.get_version_diff(slug, resolved, version_id, publisher_q=request.publisher_q())


@router.get(
    "content/{category}/{slug}/versions/{version_id}/pending-diff/",
    response={
        200: list[ChangeOut],
        400: NinjaErrorResponse[Literal["version_not_editable"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
@paginate
def pending_diff(request: Request, category: str, slug: str, version_id: int):
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    return service.get_pending_changes(slug, resolved, version_id, publisher_q=request.publisher_q())


@router.post(
    "content/{category}/{slug}/versions/{version_id}/publish/",
    response={
        200: DraftVersionOut,
        400: NinjaErrorResponse[Literal["version_not_editable"]]
        | NinjaErrorResponse[Literal["no_changes_to_publish"]]
        | NinjaErrorResponse[Literal["commit_message_required"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def publish_draft(request: Request, category: str, slug: str, version_id: int, data: PublishIn) -> AssetVersion:
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    return service.publish_draft(
        slug,
        resolved,
        version_id,
        message=data.message,
        publisher_q=request.publisher_q(),
    )


@router.delete(
    "content/{category}/{slug}/versions/{version_id}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["version_not_editable"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def discard_draft(request: Request, category: str, slug: str, version_id: int) -> tuple[int, None]:
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    service.discard_draft(slug, resolved, version_id, publisher_q=request.publisher_q())
    return 204, None


@router.post(
    "content/{category}/{slug}/versions/{version_id}/restore/",
    response={
        200: DraftVersionOut,
        400: NinjaErrorResponse[Literal["version_not_restorable"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def restore_version(request: Request, category: str, slug: str, version_id: int) -> AssetVersion:
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    return service.restore_version(
        slug,
        resolved,
        version_id,
        created_by_id=getattr(request.user, "id", None),
        publisher_q=request.publisher_q(),
    )


@router.get(
    "content/{category}/{slug}/versions/{version_id}/export/",
    response={
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def export_version(request: Request, category: str, slug: str, version_id: int):
    """Download a version's content as CSV (per-ayah entries).

    Falls back to the version's uploaded file when it has no per-ayah entries.
    """
    resolved = _resolve_for_version(category, request, slug, version_id, write=False)
    service = AssetContentService()
    version = service.get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())

    if not version.entries.exists():
        # A pruned commit: reconstruct its snapshot from deltas for download.
        snapshot = service.repo.reconstruct_entries(version)
        if snapshot:
            content = service.repo.snapshot_to_csv_bytes(snapshot, verbose=True)
        elif version.file_url:
            return HttpResponseRedirect(version.file_url.url)
        else:
            raise ItqanError(
                error_name="version_not_found",
                message=_("This version has no downloadable content."),
                status_code=404,
            )
    else:
        content = service.repo.entries_to_csv_bytes(version, verbose=True)
    # Name the file {english name}-{language}-{version} for easy identification.
    language_code = version.asset_language.language if version.asset_language_id else version.asset.language
    english_name = version.asset.name_en or slug
    filename = "_".join(f"{english_name}-{language_code}-{version.name}.csv".split())
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    # content_disposition_header safely handles non-ASCII (Arabic) and quoted names.
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response
