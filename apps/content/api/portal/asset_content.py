"""Portal endpoints for per-ayah editing of text assets (translations & tafsirs).

One router serves both categories, keyed by a ``{category}`` path segment, so
the draft / entries / publish / discard flow lives in a single place.
"""

from typing import Literal

from django.http import HttpResponse, HttpResponseRedirect
from django.utils.http import content_disposition_header
from django.utils.translation import gettext_lazy as _
from ninja import Query, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime, Field

from apps.content.models import AssetTemplateChoice, AssetVersion, AssetVersionEntry, CategoryChoice
from apps.content.services.asset_content import AssetContentService
from apps.content.services.asset_language_access import require_language, require_version_language
from apps.content.services.asset_templates import unit_spec_for
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.paginations import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.quran.models import Ayah, Sura, Word

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])

# What a caller needs to do with the asset: read it, change its metadata, or
# change its text. Text edits have their own per-category permission.
Access = Literal["read", "metadata", "content"]

# Path segment -> (category, {access: permission}).
_CATEGORY_CONFIG: dict[str, tuple[CategoryChoice, dict[str, PermissionChoice]]] = {
    "translations": (
        CategoryChoice.TRANSLATION,
        {
            "read": PermissionChoice.PORTAL_READ_TRANSLATION,
            "metadata": PermissionChoice.PORTAL_UPDATE_TRANSLATION,
            "content": PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT,
        },
    ),
    "tafsirs": (
        CategoryChoice.TAFSIR,
        {
            "read": PermissionChoice.PORTAL_READ_TAFSIR,
            "metadata": PermissionChoice.PORTAL_UPDATE_TAFSIR,
            "content": PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT,
        },
    ),
}


def _resolve(category: str, request: Request, *, access: Access) -> CategoryChoice:
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
    resolved, permissions = config
    check_permission(request.user, permissions[access], raise_exception=True)
    return resolved


def _resolve_for_version(
    category: str, request: Request, slug: str, version_id: int, *, access: Access
) -> CategoryChoice:
    """``_resolve`` plus the per-language gate for a version-scoped operation.

    These endpoints address content by version id rather than by language, so the
    filtered language list does not constrain them on its own: without this check
    an unassigned language's content would be reachable by id alone. Reads are
    gated as well as writes, for that reason.
    """
    resolved = _resolve(category, request, access=access)
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
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    reference_text: str
    sura: int | None = None
    aya: int | None = None
    text: str
    source_text: str | None = None
    order: int


def _entries_to_out(entries: list[AssetVersionEntry], template: str, source_text_by_unit: dict[int, str]) -> list[dict]:
    """Build ``EntryOut``-shaped dicts for a batch of persisted entries.

    Resolves each entry's related unit (ayah / sura / word) via one bulk
    query per unit kind rather than lazily per row: ``bulk_create``'d
    instances carry no cached FK, so per-row ``entry.ayah`` access would cost
    one query per changed row. Dispatches on whichever unit column is set,
    mirroring the four label / reference-text formats ``UnitSpec._to_row``
    builds for the canonical read path (``apps.content.services.asset_templates``).

    ``order`` is the unit's own id/number (matching ``UnitSpec._to_row``,
    which the GET path uses), not the entry's stored ``order`` column, so a
    row sorts the same whether it came back from GET or PATCH.
    """
    ayah_ids = [entry.ayah_id for entry in entries if entry.ayah_id is not None]
    sura_ids = [entry.sura_id for entry in entries if entry.sura_id is not None]
    word_ids = [entry.word_id for entry in entries if entry.word_id is not None]
    ayahs = Ayah.objects.in_bulk(ayah_ids)
    suras = Sura.objects.in_bulk(sura_ids)
    words = Word.objects.select_related("ayah").in_bulk(word_ids)

    rows = []
    for entry in entries:
        if entry.sura_id is not None:
            sura = suras[entry.sura_id]
            label = f"{entry.sura_id}. {sura.transliterated_name}"
            reference_text = sura.name
            sura_field, aya_field = entry.sura_id, None
        elif entry.ayah_id is not None:
            ayah = ayahs[entry.ayah_id]
            label = f"{ayah.sura_id}:{ayah.number_in_sura}"
            reference_text = ayah.text
            sura_field, aya_field = ayah.sura_id, ayah.number_in_sura
        elif entry.word_id is not None:
            word = words[entry.word_id]
            label = f"{word.sura_id}:{word.ayah.number_in_sura}:{word.position_in_ayah}"
            reference_text = word.text
            sura_field, aya_field = word.sura_id, word.ayah.number_in_sura
        else:
            label = _("Page {number}").format(number=entry.page_no)
            reference_text = ""
            sura_field, aya_field = None, None
        rows.append(
            {
                "unit_type": template,
                "unit_id": entry.unit_id,
                "label": label,
                "reference_text": reference_text,
                "sura": sura_field,
                "aya": aya_field,
                "text": entry.text,
                "source_text": source_text_by_unit.get(entry.unit_id),
                "order": entry.unit_id,
            }
        )
    return rows


class EntryPatchRow(Schema):
    unit_id: int
    text: str = ""


class EntriesPatchIn(Schema):
    rows: list[EntryPatchRow] = Field(default_factory=list)


class PublishIn(Schema):
    message: str


class ChangeOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    change_type: str
    old_text: str
    new_text: str
    # A reviewer's outcome for this change (committed versions only).
    review_state: str = "unreviewed"
    review_comment: str = ""
    reviewed_by: str | None = None
    reviewed_at: AwareDatetime | None = None


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
    resolved = _resolve(category, request, access="content")
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


class EntriesPageOut(Schema):
    """Mirrors NinjaPagination.Output so the envelope is unchanged."""

    results: list[EntryOut]
    count: int


@router.get(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: EntriesPageOut,
        400: NinjaErrorResponse[Literal["asset_template_missing"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def list_entries(
    request: Request,
    category: str,
    slug: str,
    version_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1),
    sura: int | None = None,
):
    resolved = _resolve_for_version(category, request, slug, version_id, access="read")
    service = AssetContentService()
    page_size = min(page_size, MAX_PAGE_SIZE)
    rows, count = service.get_entries_page(
        slug,
        resolved,
        version_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        sura=sura,
        publisher_q=request.publisher_q(),
    )
    return {"results": rows, "count": count}


@router.patch(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: list[EntryOut],
        400: NinjaErrorResponse[Literal["version_not_editable"]]
        | NinjaErrorResponse[Literal["unit_not_in_template"]]
        | NinjaErrorResponse[Literal["asset_template_missing"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def patch_entries(request: Request, category: str, slug: str, version_id: int, data: EntriesPatchIn) -> list[dict]:
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    rows = [row.model_dump() for row in data.rows]
    changed = service.upsert_entries(slug, resolved, version_id, rows, publisher_q=request.publisher_q())
    template, source_text_by_unit = service.get_patch_response_context(
        slug, resolved, version_id, changed, publisher_q=request.publisher_q()
    )
    return _entries_to_out(changed, template, source_text_by_unit)


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
    resolved = _resolve_for_version(category, request, slug, version_id, access="read")
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
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
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
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
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
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
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
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
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
    """Download a version's content as CSV, in the asset's template columns.

    Falls back to the version's uploaded file when it has no entries.
    """
    resolved = _resolve_for_version(category, request, slug, version_id, access="read")
    service = AssetContentService()
    version = service.get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())

    spec = unit_spec_for(version.asset)
    if not version.entries.exists():
        # A pruned commit: reconstruct its snapshot from deltas for download.
        snapshot = service.repo.reconstruct_entries(version)
        if snapshot:
            content = service.repo.snapshot_to_csv_bytes(snapshot, spec, asset=version.asset, verbose=True)
        elif version.file_url:
            return HttpResponseRedirect(version.file_url.url)
        else:
            raise ItqanError(
                error_name="version_not_found",
                message=_("This version has no downloadable content."),
                status_code=404,
            )
    else:
        content = service.repo.entries_to_csv_bytes(version, spec, verbose=True)
    # Name the file {english name}-{language}-{version} for easy identification.
    language_code = version.asset_language.language if version.asset_language_id else version.asset.language
    english_name = version.asset.name_en or slug
    filename = "_".join(f"{english_name}-{language_code}-{version.name}.csv".split())
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    # content_disposition_header safely handles non-ASCII (Arabic) and quoted names.
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response
