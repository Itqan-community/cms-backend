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
from ninja.schema import DjangoGetter
from pydantic import AwareDatetime, ConfigDict, Field, Json, model_validator

from apps.content.models import (
    GROUP_TEMPLATES,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    VersionStateChoice,
)
from apps.content.services.asset_content import (
    AssetContentService,
    PatchResponseContext,
    VersionBump,
    cell_fields,
    changed_fields,
    column_reorder_requires_major,
    group_fields,
)
from apps.content.services.asset_language_access import require_language, require_version_language
from apps.content.services.asset_templates import (
    FIRST_COLUMN,
    ColumnFilter,
    EntryFilters,
    NumberCondition,
    NumberFilterType,
    QuranPosition,
    TextCondition,
    TextFilterType,
    unit_spec_for,
    unit_spec_for_template,
)
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.paginations import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import check_permission
from apps.core.permissions import PermissionChoice
from apps.quran.models import Ayah, Surah, Word

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])

# What a caller needs to do with the asset: read it, change its metadata, change
# its text, or choose which approved version consumers see. Text edits have their
# own per-category permission; publishing is one permission for both categories.
Access = Literal["read", "metadata", "content", "publish"]

# Path segment -> (category, {access: permission}).
_CATEGORY_CONFIG: dict[str, tuple[CategoryChoice, dict[str, PermissionChoice]]] = {
    "translations": (
        CategoryChoice.TRANSLATION,
        {
            "read": PermissionChoice.PORTAL_READ_TRANSLATION,
            "metadata": PermissionChoice.PORTAL_UPDATE_TRANSLATION,
            "content": PermissionChoice.PORTAL_EDIT_TRANSLATION_CONTENT,
            "publish": PermissionChoice.PORTAL_PUBLISH_CONTENT,
        },
    ),
    "tafsirs": (
        CategoryChoice.TAFSIR,
        {
            "read": PermissionChoice.PORTAL_READ_TAFSIR,
            "metadata": PermissionChoice.PORTAL_UPDATE_TAFSIR,
            "content": PermissionChoice.PORTAL_EDIT_TAFSIR_CONTENT,
            "publish": PermissionChoice.PORTAL_PUBLISH_CONTENT,
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
    return _resolve_version(category, request, slug, version_id, access=access)[0]


def _resolve_version(
    category: str, request: Request, slug: str, version_id: int, *, access: Access
) -> tuple[CategoryChoice, AssetVersion]:
    """``_resolve_for_version`` that also returns the version it looked up, so an
    endpoint the editor calls often doesn't load the asset and version twice."""
    resolved = _resolve(category, request, access=access)
    version = AssetContentService().get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())
    require_version_language(request.user, version.asset, version)
    return resolved, version


class VersionTextOut(Schema):
    """A tafsir/translation version's name (label) and summary, in English and Arabic."""

    label_en: str
    label_ar: str
    summary_en: str
    summary_ar: str

    # The translated columns are nullable; an unset language reads as empty.
    @staticmethod
    def resolve_label_en(obj: AssetVersion) -> str:
        return obj.label_en or ""

    @staticmethod
    def resolve_label_ar(obj: AssetVersion) -> str:
        return obj.label_ar or ""

    @staticmethod
    def resolve_summary_en(obj: AssetVersion) -> str:
        return obj.summary_en or ""

    @staticmethod
    def resolve_summary_ar(obj: AssetVersion) -> str:
        return obj.summary_ar or ""


class VersionTextIn(Schema):
    label_en: str = Field(default="", max_length=255)
    label_ar: str = Field(default="", max_length=255)
    summary_en: str = ""
    summary_ar: str = ""


class DraftVersionOut(VersionTextOut):
    id: int
    asset_id: int
    language: str
    # Version number ("major.minor"); blank while the version is a draft.
    name: str
    state: str
    entries_count: int
    has_changes: bool
    created_at: AwareDatetime
    # Text columns in file order: the draft's are the asset's current ones; a
    # committed version's are frozen.
    column_keys: list[str]
    # Columns of the previous version were reordered: committing needs a major bump.
    requires_major: bool = False
    # The asset's unit template (ayah/surah/word/page): the editor builds its columns
    # from it before the first page of entries arrives.
    template: str | None = None

    @staticmethod
    def resolve_template(obj: AssetVersion) -> str | None:
        return obj.asset.template

    @staticmethod
    def resolve_column_keys(obj: AssetVersion) -> list[str]:
        return obj.resolved_column_keys

    @staticmethod
    def resolve_requires_major(obj: AssetVersion) -> bool:
        if obj.state != VersionStateChoice.DRAFT:
            return False
        return column_reorder_requires_major(obj.asset, obj.resolved_language)

    @staticmethod
    def resolve_language(obj: AssetVersion) -> str:
        return obj.asset_language.language if obj.asset_language_id else obj.asset.language

    @staticmethod
    def resolve_entries_count(obj: AssetVersion) -> int:
        return obj.entries.count()

    @staticmethod
    def resolve_has_changes(obj: AssetVersion) -> bool:
        return obj.content_edited


class QuranPositionOut(Schema):
    surah: int
    ayah: int
    word: int | None = None


class QuranPositionIn(Schema):
    surah: int = Field(ge=1)
    ayah: int = Field(ge=1)
    word: int | None = Field(default=None, ge=1)

    def to_position(self) -> QuranPosition:
        return QuranPosition(surah=self.surah, ayah=self.ayah, word=self.word)


class GroupRangeIn(Schema):
    start: QuranPositionIn
    end: QuranPositionIn


class GroupExtendIn(Schema):
    # Grow (1) or shrink (-1) the group's end by one ayah / word.
    by: Literal[1, -1]


class GroupIn(GroupRangeIn):
    # The group's first text, per column key; at least one must be non-blank.
    cells: dict[str, str] = Field(default_factory=dict)


class EntryOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    reference_text: str
    surah: int | None = None
    ayah: int | None = None
    # Every text column's cell ("" when empty), keyed by column key.
    cells: dict[str, str]
    # The first column; kept for clients that predate columns.
    text: str
    # Translations only: the source language's cells / first column (read-only).
    source_cells: dict[str, str] | None = None
    source_text: str | None = None
    order: int
    # A cell differs from the latest published version (always False
    # outside drafts); ``changed_columns`` names those cells' columns.
    changed: bool = False
    changed_columns: list[str] = []
    # Group templates only: the range's ends, and whether a translated language
    # holds text for a range its source no longer has.
    group_from: QuranPositionOut | None = None
    group_to: QuranPositionOut | None = None
    orphaned: bool = False


def _group_entries_to_out(entries: list[AssetVersionEntry], context: PatchResponseContext) -> list[dict]:
    """``_entries_to_out`` for a group template: one row per range, built like
    the read path's (``UnitSpec.group_rows``). Patched and added groups are
    never orphaned: translations may only write their source's ranges."""
    keys = list(dict.fromkeys(entry.unit_id for entry in entries))
    rows = unit_spec_for_template(context.template).group_rows(keys, dict.fromkeys(keys, False))
    return [
        {
            "unit_type": context.template,
            "unit_id": unit.unit_id,
            "label": unit.label,
            "reference_text": unit.reference_text,
            "surah": unit.surah,
            "ayah": unit.ayah,
            **cell_fields(unit.unit_id, context.column_keys, context.cells, context.source_cells),
            "order": unit.order,
            **changed_fields(unit.unit_id, context.column_keys, context.changed_cells),
            **group_fields(unit),
        }
        for unit in rows
    ]


def _entries_to_out(entries: list[AssetVersionEntry], context: PatchResponseContext) -> list[dict]:
    """Build ``EntryOut``-shaped dicts for the units of a batch of persisted entries,
    one row per unit (a patch may touch several columns of the same unit).

    Resolves each entry's related unit (ayah / surah / word) via one bulk
    query per unit kind rather than lazily per row: ``bulk_create``'d
    instances carry no cached FK, so per-row ``entry.ayah`` access would cost
    one query per changed row. Dispatches on whichever unit column is set,
    mirroring the four label / reference-text formats ``UnitSpec._to_row``
    builds for the canonical read path (``apps.content.services.asset_templates``).

    ``order`` is the unit's own id/number (matching ``UnitSpec._to_row``,
    which the GET path uses), not the entry's stored ``order`` column, so a
    row sorts the same whether it came back from GET or PATCH.
    """
    if context.template in GROUP_TEMPLATES:
        return _group_entries_to_out(entries, context)
    ayah_ids = [entry.ayah_id for entry in entries if entry.ayah_id is not None]
    surah_ids = [entry.surah_id for entry in entries if entry.surah_id is not None]
    word_ids = [entry.word_id for entry in entries if entry.word_id is not None]
    ayahs = Ayah.objects.in_bulk(ayah_ids)
    surahs = Surah.objects.in_bulk(surah_ids)
    words = Word.objects.select_related("ayah").in_bulk(word_ids)

    rows = []
    seen: set[int] = set()
    for entry in entries:
        if entry.unit_id in seen:
            continue
        seen.add(entry.unit_id)
        if entry.surah_id is not None:
            surah = surahs[entry.surah_id]
            label = f"{entry.surah_id}. {surah.transliterated_name}"
            reference_text = surah.name
            surah_field, ayah_field = entry.surah_id, None
        elif entry.ayah_id is not None:
            ayah = ayahs[entry.ayah_id]
            label = f"{ayah.surah_id}:{ayah.number_in_surah}"
            reference_text = ayah.text
            surah_field, ayah_field = ayah.surah_id, ayah.number_in_surah
        elif entry.word_id is not None:
            word = words[entry.word_id]
            label = f"{word.surah_id}:{word.ayah.number_in_surah}:{word.position_in_ayah}"
            reference_text = word.text
            surah_field, ayah_field = word.surah_id, word.ayah.number_in_surah
        else:
            label = _("Page {number}").format(number=entry.page_no)
            reference_text = ""
            surah_field, ayah_field = None, None
        rows.append(
            {
                "unit_type": context.template,
                "unit_id": entry.unit_id,
                "label": label,
                "reference_text": reference_text,
                "surah": surah_field,
                "ayah": ayah_field,
                **cell_fields(entry.unit_id, context.column_keys, context.cells, context.source_cells),
                "order": entry.unit_id,
                **changed_fields(entry.unit_id, context.column_keys, context.changed_cells),
            }
        )
    return rows


class EntryPatchRow(Schema):
    unit_id: int
    # The text column; omitted means the asset's first column.
    column: str | None = None
    text: str = ""


class EntriesPatchIn(Schema):
    rows: list[EntryPatchRow] = Field(default_factory=list)


class PublishIn(Schema):
    # The commit message is the version's summary: at least one language is required.
    summary_en: str = ""
    summary_ar: str = ""
    # Version name per language; omitted keeps the draft's.
    label_en: str | None = Field(default=None, max_length=255)
    label_ar: str | None = Field(default=None, max_length=255)
    # Starts the language's number sequence; ignored once it has a version.
    version_number: str | None = Field(default=None, max_length=20)
    bump: VersionBump = "minor"


class RestoreIn(Schema):
    bump: VersionBump = "minor"


class SetPublishedIn(Schema):
    # Required when going back to an earlier version; the itqan CLI shows it to
    # projects still locked to a version rolled back past.
    reason: str = Field(default="", max_length=500)


class ChangeOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    # The text column of the changed cell.
    column: str
    change_type: str
    old_text: str
    new_text: str
    # A reviewer's outcome for a stored change: approved / commented / unreviewed.
    # None for diffs computed on the fly (drafts, commits that predate change
    # tracking), which have nothing to review.
    review_state: str | None = None
    review_comment: str = ""
    reviewed_by: str | None = None
    reviewed_at: AwareDatetime | None = None


class DraftIn(Schema):
    # Omitted: the source language, so the editor can open before it lists the languages.
    language: str | None = None


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
    language = asset.language if data.language is None else data.language
    require_language(request.user, asset, language)
    return service.get_or_create_draft(
        slug,
        resolved,
        language=language,
        created_by_id=getattr(request.user, "id", None),
        publisher_q=request.publisher_q(),
    )


class GridTextConditionIn(Schema):
    """One AG Grid text-filter condition, as the grid's filter model sends it."""

    filter_type: Literal["text"] = Field("text", alias="filterType")
    kind: TextFilterType = Field(alias="type")
    value: str = Field("", alias="filter")

    def to_condition(self) -> TextCondition:
        return TextCondition(type=self.kind, value=self.value)


class GridNumberConditionIn(Schema):
    """One AG Grid number-filter condition, as the grid's filter model sends it."""

    filter_type: Literal["number"] = Field("number", alias="filterType")
    kind: NumberFilterType = Field(alias="type")
    value: int | None = Field(None, alias="filter")
    value_to: int | None = Field(None, alias="filterTo")

    @model_validator(mode="after")
    def _require_operands(self) -> "GridNumberConditionIn":
        if self.kind not in ("blank", "notBlank") and self.value is None:
            raise ValueError("`filter` is required for this number filter type.")
        if self.kind == "inRange" and self.value_to is None:
            raise ValueError("`filterTo` is required for an inRange number filter.")
        return self

    def to_condition(self) -> NumberCondition:
        return NumberCondition(type=self.kind, value=self.value, value_to=self.value_to)


class GridTextCombinedIn(Schema):
    """Two text conditions joined by AND / OR (AG Grid's combined model)."""

    filter_type: Literal["text"] = Field("text", alias="filterType")
    operator: Literal["AND", "OR"]
    conditions: list[GridTextConditionIn] = Field(min_length=1, max_length=2)


class GridNumberCombinedIn(Schema):
    """Two number conditions joined by AND / OR (AG Grid's combined model)."""

    filter_type: Literal["number"] = Field("number", alias="filterType")
    operator: Literal["AND", "OR"]
    conditions: list[GridNumberConditionIn] = Field(min_length=1, max_length=2)


GridTextFilterIn = GridTextConditionIn | GridTextCombinedIn
GridNumberFilterIn = GridNumberConditionIn | GridNumberCombinedIn


def _column_filter(
    model: GridTextFilterIn | GridNumberFilterIn | None,
) -> ColumnFilter | None:
    if model is None:
        return None
    if isinstance(model, GridTextCombinedIn | GridNumberCombinedIn):
        return ColumnFilter(
            conditions=tuple(condition.to_condition() for condition in model.conditions),
            operator=model.operator,
        )
    return ColumnFilter(conditions=(model.to_condition(),))


class EntriesFilterModelIn(Schema):
    """The entries grid's AG Grid filter model, keyed by column id.

    Text columns are ``cell__<key>`` (the version's own cells) and
    ``source__<key>`` (the source language's); ``text`` / ``source_text`` name
    the first column. ``unit_surah`` is the unit column's surah-name dropdown and
    ``surah`` the surah-number column; both filter the surah number. Unknown
    grid columns are rejected so a typo surfaces as a 400 instead of silently
    returning unfiltered rows; an unknown text column is rejected by the
    service (``unknown_filter_column``), which knows the asset's columns.
    """

    model_config = ConfigDict(extra="forbid")

    text: GridTextFilterIn | None = None
    reference_text: GridTextFilterIn | None = None
    source_text: GridTextFilterIn | None = None
    unit_surah: GridNumberFilterIn | None = None
    surah: GridNumberFilterIn | None = None
    ayah: GridNumberFilterIn | None = None
    cells: dict[str, GridTextFilterIn] = Field(default_factory=dict)
    source_cells: dict[str, GridTextFilterIn] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _collect_column_filters(cls, data: object) -> object:
        """Gather the ``cell__<key>`` / ``source__<key>`` grid columns."""
        if isinstance(data, DjangoGetter):  # ninja's Schema wraps the raw dict
            data = data._obj
        if not isinstance(data, dict):
            return data
        data = dict(data)
        cells: dict[str, object] = {}
        source_cells: dict[str, object] = {}
        for name in list(data):
            if name.startswith("cell__"):
                cells[name.removeprefix("cell__")] = data.pop(name)
            elif name.startswith("source__"):
                source_cells[name.removeprefix("source__")] = data.pop(name)
        data["cells"] = cells
        data["source_cells"] = source_cells
        return data

    def to_filters(self) -> EntryFilters:
        cells = {key: _column_filter(model) for key, model in self.cells.items()}
        source_cells = {key: _column_filter(model) for key, model in self.source_cells.items()}
        if self.text is not None:
            cells.setdefault(FIRST_COLUMN, _column_filter(self.text))
        if self.source_text is not None:
            source_cells.setdefault(FIRST_COLUMN, _column_filter(self.source_text))
        return EntryFilters(
            cells=cells,
            reference_text=_column_filter(self.reference_text),
            source_cells=source_cells,
            unit_surah=_column_filter(self.unit_surah),
            surah=_column_filter(self.surah),
            ayah=_column_filter(self.ayah),
        )


class EntriesPageOut(Schema):
    """Mirrors NinjaPagination.Output so the envelope is unchanged."""

    results: list[EntryOut]
    count: int


@router.get(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: EntriesPageOut,
        400: NinjaErrorResponse[Literal["asset_template_missing"]]
        | NinjaErrorResponse[Literal["unknown_filter_column"]],
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
    surah: int | None = None,
    filters: Json[EntriesFilterModelIn] | None = Query(None),
):
    _, version = _resolve_version(category, request, slug, version_id, access="read")
    service = AssetContentService()
    page_size = min(page_size, MAX_PAGE_SIZE)
    rows, count = service.get_entries_page(
        version,
        offset=(page - 1) * page_size,
        limit=page_size,
        surah=surah,
        filters=filters.to_filters() if filters is not None else None,
    )
    return {"results": rows, "count": count}


@router.patch(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: list[EntryOut],
        400: NinjaErrorResponse[Literal["version_not_editable"]]
        | NinjaErrorResponse[Literal["unit_not_in_template"]]
        | NinjaErrorResponse[Literal["unknown_column"]]
        | NinjaErrorResponse[Literal["asset_template_missing"]]
        | NinjaErrorResponse[Literal["group_not_in_source"]],
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
    context = service.get_patch_response_context(slug, resolved, version_id, changed, publisher_q=request.publisher_q())
    return _entries_to_out(changed, context)


_GROUP_400 = (
    NinjaErrorResponse[Literal["version_not_editable"]]
    | NinjaErrorResponse[Literal["template_not_grouped"]]
    | NinjaErrorResponse[Literal["group_ranges_source_only"]]
    | NinjaErrorResponse[Literal["group_range_invalid"]]
    | NinjaErrorResponse[Literal["group_exists"]]
)
_GROUP_404 = (
    NinjaErrorResponse[Literal["translation_not_found"]]
    | NinjaErrorResponse[Literal["tafsir_not_found"]]
    | NinjaErrorResponse[Literal["version_not_found"]]
    | NinjaErrorResponse[Literal["unsupported_content_category"]]
)


@router.post(
    "content/{category}/{slug}/versions/{version_id}/groups/",
    response={
        200: list[EntryOut],
        400: _GROUP_400 | NinjaErrorResponse[Literal["unknown_column"]],
        404: _GROUP_404,
    },
)
def add_group(request: Request, category: str, slug: str, version_id: int, data: GroupIn) -> list[dict]:
    """Add a group (a range of ayahs / words) to a source-language draft, with its
    first text if given; a group left blank is dropped when the draft is committed."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    changed = service.add_group(
        slug,
        resolved,
        version_id,
        start=data.start.to_position(),
        end=data.end.to_position(),
        cells=data.cells,
        publisher_q=request.publisher_q(),
    )
    context = service.get_patch_response_context(slug, resolved, version_id, changed, publisher_q=request.publisher_q())
    return _entries_to_out(changed, context)


@router.post(
    "content/{category}/{slug}/versions/{version_id}/groups/next/",
    response={200: list[EntryOut], 400: _GROUP_400, 404: _GROUP_404},
)
def append_group(request: Request, category: str, slug: str, version_id: int) -> list[dict]:
    """Add a blank one-ayah (or one-word) group right after the furthest unit the
    draft's groups reach — the grid's "add next group"."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    added = service.append_group(slug, resolved, version_id, publisher_q=request.publisher_q())
    context = service.get_patch_response_context(slug, resolved, version_id, added, publisher_q=request.publisher_q())
    return _entries_to_out(added, context)


@router.post(
    "content/{category}/{slug}/versions/{version_id}/groups/{unit_id}/extend/",
    response={200: list[EntryOut], 400: _GROUP_400, 404: _GROUP_404 | NinjaErrorResponse[Literal["group_not_found"]]},
)
def extend_group(
    request: Request, category: str, slug: str, version_id: int, unit_id: int, data: GroupExtendIn
) -> list[dict]:
    """Grow or shrink a group's end by one ayah / word, keeping its text."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    moved = service.extend_group(slug, resolved, version_id, unit_id, by=data.by, publisher_q=request.publisher_q())
    context = service.get_patch_response_context(slug, resolved, version_id, moved, publisher_q=request.publisher_q())
    return _entries_to_out(moved, context)


@router.put(
    "content/{category}/{slug}/versions/{version_id}/groups/{unit_id}/",
    response={200: list[EntryOut], 400: _GROUP_400, 404: _GROUP_404 | NinjaErrorResponse[Literal["group_not_found"]]},
)
def move_group(
    request: Request, category: str, slug: str, version_id: int, unit_id: int, data: GroupRangeIn
) -> list[dict]:
    """Give a source-language draft's group a new range, keeping its text."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    moved = service.move_group(
        slug,
        resolved,
        version_id,
        unit_id,
        start=data.start.to_position(),
        end=data.end.to_position(),
        publisher_q=request.publisher_q(),
    )
    context = service.get_patch_response_context(slug, resolved, version_id, moved, publisher_q=request.publisher_q())
    return _entries_to_out(moved, context)


@router.delete(
    "content/{category}/{slug}/versions/{version_id}/groups/{unit_id}/",
    response={204: None, 400: _GROUP_400, 404: _GROUP_404 | NinjaErrorResponse[Literal["group_not_found"]]},
)
def delete_group(request: Request, category: str, slug: str, version_id: int, unit_id: int) -> tuple[int, None]:
    """Delete a draft's group. A translated language may only delete a group its source no longer has."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    AssetContentService().delete_group(slug, resolved, version_id, unit_id, publisher_q=request.publisher_q())
    return 204, None


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
    _, version = _resolve_version(category, request, slug, version_id, access="content")
    return AssetContentService().get_pending_changes(version)


@router.get(
    "content/{category}/{slug}/versions/{version_id}/",
    response={
        200: DraftVersionOut,
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def get_version(request: Request, category: str, slug: str, version_id: int) -> AssetVersion:
    """One version's name and language — e.g. for the read-only version viewer."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="read")
    return AssetContentService().get_version_or_404(slug, resolved, version_id, publisher_q=request.publisher_q())


@router.post(
    "content/{category}/{slug}/versions/{version_id}/publish/",
    response={
        200: DraftVersionOut,
        400: NinjaErrorResponse[Literal["version_not_editable"]]
        | NinjaErrorResponse[Literal["no_changes_to_publish"]]
        | NinjaErrorResponse[Literal["major_bump_required"]]
        | NinjaErrorResponse[Literal["commit_message_required"]]
        | NinjaErrorResponse[Literal["version_number_required"]]
        | NinjaErrorResponse[Literal["version_number_invalid"]]
        | NinjaErrorResponse[Literal["orphaned_groups"]],
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
        summary_en=data.summary_en,
        summary_ar=data.summary_ar,
        label_en=data.label_en,
        label_ar=data.label_ar,
        version_number=data.version_number,
        bump=data.bump,
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
        400: NinjaErrorResponse[Literal["version_not_restorable"]] | NinjaErrorResponse[Literal["major_bump_required"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def restore_version(request: Request, category: str, slug: str, version_id: int, data: RestoreIn) -> AssetVersion:
    resolved = _resolve_for_version(category, request, slug, version_id, access="content")
    service = AssetContentService()
    return service.restore_version(
        slug,
        resolved,
        version_id,
        bump=data.bump,
        created_by_id=getattr(request.user, "id", None),
        publisher_q=request.publisher_q(),
    )


@router.post(
    "content/{category}/{slug}/versions/{version_id}/set-published/",
    response={
        200: DraftVersionOut,
        400: NinjaErrorResponse[Literal["version_not_publishable"]]
        | NinjaErrorResponse[Literal["version_not_approved"]]
        | NinjaErrorResponse[Literal["version_removed"]]
        | NinjaErrorResponse[Literal["rollback_reason_required"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def set_published_version(
    request: Request, category: str, slug: str, version_id: int, data: SetPublishedIn | None = None
) -> AssetVersion:
    """Make a fully approved version the one consumers see for its language.
    Going back to an earlier version requires ``reason``."""
    resolved = _resolve_for_version(category, request, slug, version_id, access="publish")
    return AssetContentService().set_published_version(
        slug, resolved, version_id, reason=data.reason if data else "", publisher_q=request.publisher_q()
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
            content = service.repo.snapshot_to_csv_bytes(
                snapshot, spec, asset=version.asset, column_keys=version.resolved_column_keys, verbose=True
            )
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


def _csv_template_response(content: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response


@router.get(
    "content/{category}/csv-template/",
    response={
        400: NinjaErrorResponse[Literal["mushaf_layout_required"]],
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def download_csv_template(
    request: Request, category: str, template: AssetTemplateChoice, mushaf_layout_id: int | None = None
):
    """An empty CSV to fill in for a template, before the asset exists (asset
    creation): one row per surah / ayah / word / page, blank ``text``. A page
    template needs the mushaf layout, which sets the number of pages."""
    _resolve(category, request, access="read")
    page_count = None
    filename = f"{template}-template.csv"
    if template == AssetTemplateChoice.PAGE:
        if mushaf_layout_id is None:
            raise ItqanError(
                error_name="mushaf_layout_required",
                message=_("Choose a mushaf layout to download the page template."),
                status_code=400,
            )
        try:
            layout = MushafLayout.objects.get(pk=mushaf_layout_id)
        except MushafLayout.DoesNotExist as exc:
            raise ItqanError(
                error_name="mushaf_layout_not_found",
                message=_("Mushaf layout with id {id} not found.").format(id=mushaf_layout_id),
                status_code=404,
            ) from exc
        page_count = layout.page_count
        filename = "_".join(f"page-{layout.name}-template.csv".split())
    content = AssetContentService().repo.blank_template_csv_bytes(
        unit_spec_for_template(template), page_count=page_count
    )
    return _csv_template_response(content, filename)


@router.get(
    "content/{category}/{slug}/csv-template/",
    response={
        400: NinjaErrorResponse[Literal["asset_template_missing"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def download_asset_csv_template(request: Request, category: str, slug: str):
    """An empty CSV to fill in for an existing asset's template (version upload
    and replace): one row per unit of its template, blank ``text``."""
    resolved = _resolve(category, request, access="read")
    service = AssetContentService()
    asset = service._get_asset_or_404(slug, resolved, publisher_q=request.publisher_q())
    content = service.repo.blank_template_csv_bytes(
        unit_spec_for(asset),
        page_count=service.repo.page_count(asset),
        column_keys=[column.key for column in asset.text_columns()],
    )
    filename = "_".join(f"{asset.name_en or slug}-{asset.template}-template.csv".split())
    return _csv_template_response(content, filename)
