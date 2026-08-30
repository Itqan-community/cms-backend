"""Portal endpoints for per-ayah editing of text assets (translations & tafsirs).

One router serves both categories, keyed by a ``{category}`` path segment, so
the draft / entries / publish / discard flow lives in a single place.
"""

from typing import Literal

from django.http import HttpResponse, HttpResponseRedirect
from django.utils.http import content_disposition_header
from ninja import Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import AssetVersion, AssetVersionEntry, CategoryChoice
from apps.content.services.asset_content import AssetContentService
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
            message=f"Unsupported content category: {category}",
            status_code=404,
        )
    resolved, read_perm, write_perm = config
    check_permission(request.user, write_perm if write else read_perm, raise_exception=True)
    return resolved


class DraftVersionOut(Schema):
    id: int
    asset_id: int
    name: str
    summary: str
    state: str
    entries_count: int
    has_changes: bool
    created_at: AwareDatetime

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
    footnotes: str
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
    footnotes: str = ""


class EntriesPatchIn(Schema):
    rows: list[EntryPatchRow] = Field(default_factory=list)


class PublishIn(Schema):
    name: str | None = Field(default=None, max_length=255)
    summary: str | None = None


@router.post(
    "content/{category}/{slug}/draft/",
    response={
        200: DraftVersionOut,
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def get_or_create_draft(request: Request, category: str, slug: str) -> AssetVersion:
    resolved = _resolve(category, request, write=True)
    service = AssetContentService()
    return service.get_or_create_draft(
        slug,
        resolved,
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
    resolved = _resolve(category, request, write=False)
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
    resolved = _resolve(category, request, write=True)
    service = AssetContentService()
    rows = [row.model_dump() for row in data.rows]
    return service.upsert_entries(slug, resolved, version_id, rows, publisher_q=request.publisher_q())


@router.post(
    "content/{category}/{slug}/versions/{version_id}/publish/",
    response={
        200: DraftVersionOut,
        400: NinjaErrorResponse[Literal["version_not_editable"]] | NinjaErrorResponse[Literal["no_changes_to_publish"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def publish_draft(request: Request, category: str, slug: str, version_id: int, data: PublishIn) -> AssetVersion:
    resolved = _resolve(category, request, write=True)
    service = AssetContentService()
    return service.publish_draft(
        slug,
        resolved,
        version_id,
        name=data.name,
        summary=data.summary,
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
    resolved = _resolve(category, request, write=True)
    service = AssetContentService()
    service.discard_draft(slug, resolved, version_id, publisher_q=request.publisher_q())
    return 204, None


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
    resolved = _resolve(category, request, write=False)
    service = AssetContentService()
    version = service.get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())

    if not version.entries.exists():
        if version.file_url:
            return HttpResponseRedirect(version.file_url.url)
        raise ItqanError(
            error_name="version_not_found",
            message="This version has no downloadable content.",
            status_code=404,
        )

    content = service.repo.entries_to_csv_bytes(version)
    filename = f"{slug}-{version.name}.csv"
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    # content_disposition_header safely handles non-ASCII (Arabic) and quoted names.
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response
