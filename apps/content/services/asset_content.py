"""Business logic for per-ayah asset content editing (translations & tafsirs).

Flow: open editor -> get-or-create a shared server-side *draft* version (seeded
from the latest committed version) -> edit its entries -> either *commit* the
draft (newest-wins makes it the head) or *discard* it. Drafts are excluded from
every "latest / published" query (see model + Phase 0 guards), so in-progress
edits never leak to public/tenant/developers surfaces. A committed version
reaches consumers only once its changes are approved and it is explicitly
*published* (``set_published_version``).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from typing import Literal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.content.columns import CellKey, Snapshot, requires_major_bump
from apps.content.models import (
    GROUP_TEMPLATES,
    REVIEWED_CATEGORIES,
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.repositories.asset_review import AssetReviewRepository
from apps.content.services.asset_content_import import (
    AssetContentInvalidRowsError,
    AssetContentMissingColumnsError,
    AssetContentParseError,
    parse_content_file,
)
from apps.content.services.asset_templates import (
    EntryFilters,
    QuranPosition,
    UnitRow,
    UnitSpec,
    group_label,
    range_invalid_error,
    unit_spec_for,
)
from apps.content.tasks import notify_asset_version_created
from apps.content.unit_keys import decode_group_key, encode_group_key
from apps.content.version_text import VersionText
from apps.core.ninja_utils.errors import ItqanError
from apps.dependabot.tasks import dispatch_dependabot_updates_for_version

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PatchResponseContext:
    template: str
    column_keys: list[str]
    cells: Snapshot
    source_cells: Snapshot | None
    changed_cells: set[CellKey]


def cell_fields(unit_id: int, keys: list[str], cells: Snapshot, source_cells: Snapshot | None) -> dict:
    """A unit's ``cells`` / ``source_cells`` (every column, "" when empty), plus
    ``text`` / ``source_text`` — its first column — for single-text clients."""
    first = keys[0]
    return {
        "cells": {key: cells.get((unit_id, key), "") for key in keys},
        "text": cells.get((unit_id, first), ""),
        "source_cells": (
            {key: source_cells.get((unit_id, key), "") for key in keys} if source_cells is not None else None
        ),
        "source_text": source_cells.get((unit_id, first)) if source_cells is not None else None,
    }


def group_fields(unit: UnitRow) -> dict:
    """A group row's range ends (``{"surah", "ayah", "word"}``) and orphan flag; empty for other templates."""
    if unit.group_from is None:
        return {}

    def position(ends: tuple[int, ...]) -> dict:
        return {"surah": ends[0], "ayah": ends[1], "word": ends[2] if len(ends) > 2 else None}

    return {"group_from": position(unit.group_from), "group_to": position(unit.group_to), "orphaned": unit.orphaned}


def changed_fields(unit_id: int, keys: list[str], changed_cells: set[CellKey]) -> dict:
    """A unit's ``changed`` flag and the keys of its ``changed_columns``, in column order."""
    columns = [key for key in keys if (unit_id, key) in changed_cells]
    return {"changed": bool(columns), "changed_columns": columns}


_NOT_FOUND_ERROR = {
    CategoryChoice.TRANSLATION: "translation_not_found",
    CategoryChoice.TAFSIR: "tafsir_not_found",
    CategoryChoice.MUSHAF: "mushaf_not_found",
    CategoryChoice.FONT: "font_not_found",
}


def import_uploaded_file_into_entries(version: AssetVersion, *, strict: bool = False) -> None:
    """Parse an uploaded version file into entries, keyed to the asset's template unit.

    Called from the translation/tafsir version create/update flow so that any
    uploaded content file also populates ``AssetVersionEntry`` rows (edits then
    happen on rows, never on the file).

    Best-effort by default: a file that cannot be parsed is logged and skipped so
    it never breaks the existing upload path. When ``strict`` is set (the
    add-language flow, which declares a ``content_file_unparseable`` error), an
    unparseable file instead raises ``ItqanError`` so the caller can reject the
    upload and roll back — a malformed file must not create an empty version.

    Reads from the *saved* ``version.file_url`` rather than the passed-in upload
    object: by the time this runs the repository has already written the upload
    to storage, which consumes the upload stream (a large ``TemporaryUploadedFile``
    ends up at EOF / closed), so re-reading the upload directly would yield empty
    bytes. Reading the persisted file is reliable for uploads of any size.
    """
    saved = getattr(version, "file_url", None)
    if not saved:
        if strict:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("The uploaded file could not be read."),
                status_code=400,
            )
        return
    try:
        saved.open("rb")
        try:
            raw = saved.read()
        finally:
            saved.close()
    except Exception as exc:
        logger.warning(f"Could not read saved version file for entries [version_id={version.pk}]")
        if strict:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("The uploaded file could not be read."),
                status_code=400,
            ) from exc
        return
    spec = unit_spec_for(version.asset)
    try:
        parsed = parse_content_file(
            raw, spec, version.asset, strict=strict, allowed_unit_ids=source_group_keys(version)
        )
    except AssetContentMissingColumnsError as exc:
        # Raised whatever `strict` says: a version missing a column would drop all its cells.
        logger.info(f"Uploaded file is missing columns [version_id={version.pk}, missing={exc.missing}]")
        raise missing_columns_error(exc) from exc
    except AssetContentInvalidRowsError as exc:
        # Only raised in strict mode: rows whose text a lenient parse would drop
        # could reach consumers without ever being reviewed.
        logger.info(f"Uploaded file has invalid rows [version_id={version.pk}, rows={list(exc.rows)}]")
        shown = ", ".join(str(row) for row in list(exc.rows)[:10])
        raise ItqanError(
            error_name="content_file_invalid_rows",
            message=_(
                "Some rows can't be used: they repeat a unit or range, name a unit that doesn't exist, end "
                "before they start, use a range the source language doesn't have, or can't be read. Fix "
                "row(s) {rows} and upload again."
            ).format(rows=shown + (" …" if len(exc.rows) > 10 else "")),
            status_code=400,
            extra={"rows": {str(row): reason for row, reason in exc.rows.items()}},
        ) from exc
    except AssetContentParseError as exc:
        logger.info(f"Uploaded file not parsed into entries [version_id={version.pk}, reason={exc}]")
        if strict:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("The uploaded file could not be parsed into content entries."),
                status_code=400,
            ) from exc
        return
    entries_count = AssetContentRepository().replace_entries_from_parsed(version, spec, parsed)
    logger.info(f"Uploaded file imported into entries [version_id={version.pk}, entries={entries_count}]")


def source_group_keys(version: AssetVersion) -> set[int] | None:
    """The ranges a translated language of a group asset may use: its source head's.

    ``None`` (no restriction) for any other version. With no committed source
    version the set is empty, so every row is refused.
    """
    asset = version.asset
    if asset.template not in GROUP_TEMPLATES or version.asset_language is None or version.asset_language.is_source:
        return None
    head = asset.get_latest_version(asset.language)
    if head is None:
        return set()
    if head.entries.exists():
        # The head keeps its full entries: read only the ranges, never the text.
        return unit_spec_for(asset).stored_ranges(head, with_text=True)
    return {unit_id for (unit_id, _key), text in AssetContentRepository().reconstruct_entries(head).items() if text}


def missing_columns_error(exc: AssetContentMissingColumnsError) -> ItqanError:
    return ItqanError(
        error_name="content_file_missing_columns",
        message=_("The file is missing these columns: {columns}.").format(columns=", ".join(exc.missing)),
        status_code=400,
        extra={"missing": exc.missing},
    )


def column_reorder_requires_major(asset: Asset, language: str) -> bool:
    """Whether the next commit of ``language`` must be a major version: the
    asset's columns were reordered since the language's latest committed version."""
    previous = asset.get_latest_version(language)
    if previous is None:
        return False
    current = [column.key for column in asset.text_columns()]
    return requires_major_bump(previous.resolved_column_keys, current)


def _major_bump_required() -> ItqanError:
    return ItqanError(
        error_name="major_bump_required",
        message=_(
            "Columns were reordered since the last version. Reordering changes the file layout, "
            "so this must be a major version."
        ),
        status_code=400,
    )


def forbid_minor_after_column_reorder(asset: Asset, language: str, bump: VersionBump) -> None:
    if bump == "minor" and column_reorder_requires_major(asset, language):
        raise _major_bump_required()


def adopt_current_columns(version: AssetVersion) -> None:
    """Give a committed version whose file is being replaced the asset's current
    columns, which the new file is parsed with — so its stored file carries every
    column reviewers approve. Its number is already issued, so columns reordered
    since it was committed are refused: that layout change needs a major version."""
    if not version.column_keys:
        return  # a draft follows the asset's columns anyway
    current = [column.key for column in version.asset.ensure_text_columns()]
    if requires_major_bump(version.column_keys, current):
        raise _major_bump_required()
    if current != version.column_keys:
        AssetContentRepository().set_column_keys(version, current)


def forbid_published_version_change(version: AssetVersion) -> None:
    """Consumers are served the published version, so its content cannot be
    replaced and it cannot be deleted — publish another version first."""
    if AssetLanguage.objects.filter(published_version=version).exists():
        raise ItqanError(
            error_name="version_is_published",
            message=_("This version is published. Publish another version first."),
            status_code=400,
        )


def forbid_history_rewrite(version: AssetVersion) -> None:
    """Only the newest committed version of a language may be replaced or deleted.

    History is append-only: each commit's stored changes are a delta against its
    predecessor, which is what approval (``pending_cells_by_version``) and the
    reconstruction of pruned versions replay. Rewriting or removing a version
    that later versions build on would silently change what those versions
    contain — and could make unreviewed text look approved in them.
    """
    if version.state != VersionStateChoice.PUBLISHED:
        return  # drafts are not part of the history
    later = AssetVersion.objects.filter(
        asset_id=version.asset_id,
        asset_language_id=version.asset_language_id,
        state=VersionStateChoice.PUBLISHED,
    ).filter(Q(created_at__gt=version.created_at) | Q(created_at=version.created_at, id__gt=version.id))
    if later.exists():
        raise ItqanError(
            error_name="version_not_latest",
            message=_("Only the newest version can be changed or deleted, because later versions are built on it."),
            status_code=400,
        )


def lock_version_for_content_change(version: AssetVersion) -> AssetVersion:
    """Lock ``version``'s row and check its content may still change.

    Must run inside a transaction. Publishing takes the same lock, so a file
    replacement or deletion and a publish of the same version are serialized and
    the later one re-checks against the other's outcome — a version can't be
    published and then changed underneath consumers, or changed after its
    approval was checked.
    """
    locked = AssetVersion.objects.select_for_update().get(pk=version.pk)
    forbid_published_version_change(locked)
    forbid_history_rewrite(locked)
    return locked


def set_version_language(version: AssetVersion, language: str | None) -> None:
    """Tag an uploaded version with a specific (already-registered) language.

    A no-op when ``language`` is falsy — the version keeps the source language
    assigned by ``AssetVersion.save()``. Raises ``language_not_available`` (404)
    if the language is not one of the asset's registered languages.
    """
    if not language:
        return
    from apps.content.services.asset_language import AssetLanguageService

    asset_language = AssetLanguageService().get_asset_language_or_404(version.asset, language)
    if version.asset_language_id != asset_language.id:
        version.asset_language = asset_language
        version.save(update_fields=["asset_language", "updated_at"])


VersionBump = Literal["minor", "major"]

# A tafsir / translation version number: "major.minor", e.g. "7.0".
_VERSION_NUMBER_RE = re.compile(r"^(\d{1,9})\.(\d{1,9})$")


def parse_version_number(value: str) -> tuple[int, int] | None:
    """``"7.10"`` -> ``(7, 10)``; ``None`` when ``value`` is not a version number."""
    match = _VERSION_NUMBER_RE.match(value.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def next_version_number(existing_names: list[str], *, start: str | None, bump: VersionBump) -> str:
    """The number the next version in a sequence gets.

    An empty sequence starts at the caller-chosen ``start``; otherwise the highest
    existing number is bumped (minor: 7.1 -> 7.2, major: 7.1 -> 8.0) and ``start``
    is ignored.
    """
    numbers = [number for number in map(parse_version_number, existing_names) if number is not None]
    if numbers:
        major, minor = max(numbers)
        return f"{major + 1}.0" if bump == "major" else f"{major}.{minor + 1}"
    if not (start or "").strip():
        raise ItqanError(
            error_name="version_number_required",
            message=_("A starting version number is required for the first version."),
            status_code=400,
        )
    parsed = parse_version_number(start)
    if parsed is None:
        raise ItqanError(
            error_name="version_number_invalid",
            message=_("Version number must be in the form major.minor, e.g. 7.0."),
            status_code=400,
        )
    return f"{parsed[0]}.{parsed[1]}"


def issue_version_number(
    asset: Asset, language: str | None, *, start: str | None = None, bump: VersionBump = "minor"
) -> str:
    """Issue the next version number in ``asset``'s sequence for ``language``.

    Each (asset, language) has its own sequence; ``language=None`` means the
    source language. Must run inside a transaction: the asset row stays locked
    until it commits, so concurrent commits/uploads can't issue the same number.
    """
    repo = AssetContentRepository()
    repo.lock_asset(asset)
    names = repo.sequence_version_names(asset, language or asset.language)
    return next_version_number(names, start=start, bump=bump)


class AssetContentService:
    """Shared per-ayah content editing for text-based assets."""

    def __init__(self, repo: AssetContentRepository | None = None) -> None:
        self.repo = repo or AssetContentRepository()

    def _get_asset_or_404(self, slug: str, category: CategoryChoice, publisher_q: Q | None = None) -> Asset:
        qs = Asset.objects.all()
        if publisher_q is not None:
            qs = qs.filter(publisher_q)
        try:
            return qs.get(slug=slug, category=category, status=StatusChoice.READY)
        except Asset.DoesNotExist as exc:
            raise ItqanError(
                error_name=_NOT_FOUND_ERROR[category],
                message=_("{category} with slug {slug} not found.").format(category=category.label, slug=slug),
                status_code=404,
            ) from exc

    def _get_editable_draft_or_400(self, asset: Asset, version_id: int) -> AssetVersion:
        version = self.repo.get_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found.").format(id=version_id),
                status_code=404,
            )
        self._require_draft(version)
        return version

    @staticmethod
    def _require_draft(version: AssetVersion) -> None:
        if version.state != VersionStateChoice.DRAFT:
            raise ItqanError(
                error_name="version_not_editable",
                message=_("Only draft versions can be edited."),
                status_code=400,
            )

    def get_or_create_draft(
        self,
        slug: str,
        category: CategoryChoice,
        *,
        language: str,
        created_by_id: int | None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Return the shared draft for one language, seeding it from that
        language's latest published version. Creates the draft if none exists; if
        an existing draft predates the latest published version of the language
        (e.g. a new version was published after the draft was started), the stale
        draft is rebuilt so the editor always reflects the current content."""
        from apps.content.services.asset_language import AssetLanguageService

        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        # The source rendition is created lazily, so guarantee it exists before a
        # source-language edit; translation languages must be added first.
        asset.get_or_create_source_language()
        asset_language = AssetLanguageService().get_asset_language_or_404(asset, language)
        # Lock the asset row so concurrent editor-opens can't both create a draft
        # and violate the one-draft-per-(asset,language) constraint (which would 500).
        try:
            with transaction.atomic():
                locked_asset = Asset.objects.select_for_update().get(pk=asset.pk)
                source = locked_asset.get_latest_version(language)
                # When editing a translation, always seed from the full source
                # mushaf so the editor shows every original ayah (overlaying any
                # existing translation), even ayahs the translation hasn't reached
                # yet or that a previous sparse publish dropped. Meaningful only for
                # the ayah template — a surah/word/page translation has no mushaf
                # ayah rows to cover, and Task 6's virtual enumeration already shows
                # its full unit set without any seeded rows.
                mushaf = None
                if not asset_language.is_source and locked_asset.template == AssetTemplateChoice.AYAH:
                    mushaf = locked_asset.get_latest_version(locked_asset.language)
                existing = self.repo.get_draft(locked_asset, asset_language)
                if existing is not None:
                    is_stale = source is not None and source.created_at > existing.created_at
                    if not is_stale:
                        # Keep a translation draft covering the whole mushaf, even if
                        # it was created sparse (e.g. before full-mushaf seeding).
                        if mushaf is not None:
                            self.repo.ensure_mushaf_coverage(existing, mushaf)
                        return existing
                    # A newer version exists than this draft — discard the stale
                    # draft and rebuild it below from the current latest version.
                    logger.info(
                        f"Rebuilding stale draft [draft_id={existing.pk}, asset_id={locked_asset.pk}, "
                        f"language={language}, newer_version_id={source.pk}]"
                    )
                    self.repo.delete_version(existing)
                # A draft has no version number yet — one is issued when it is
                # committed. It inherits the source's name so the commit prefills it.
                draft = self.repo.create_draft_seeded_from(
                    locked_asset,
                    source,
                    asset_language=asset_language,
                    name="",
                    text=VersionText.of(source),
                    created_by_id=created_by_id,
                    mushaf_version=mushaf,
                )
        except IntegrityError:
            # A concurrent request created the draft between our checks — return it.
            existing = self.repo.get_draft(asset, asset_language)
            if existing is not None:
                return existing
            raise
        logger.info(
            f"Draft version created [version_id={draft.pk}, asset_id={asset.pk}, "
            f"language={language}, seeded_from={source.pk if source else None}]"
        )
        return draft

    def get_version_diff(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ) -> list[dict]:
        """Return a commit's per-ayah diff (stored delta, or computed for legacy)."""
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        return self.repo.version_diff(version)

    def get_pending_changes(self, draft: AssetVersion) -> list[dict]:
        """The uncommitted diff of a draft vs the current head — what a commit would
        record. Empty draft rows are excluded (they are dropped on commit).

        ``draft`` is the version the endpoint already resolved (see ``get_version_or_404``)."""
        self._require_draft(draft)
        asset = draft.asset
        spec = unit_spec_for(asset)
        language = draft.asset_language.language if draft.asset_language_id else asset.language
        head = asset.get_latest_version(language)
        old_map = self.repo.reconstruct_entries(head) if head is not None else {}
        new_map = {cell: text for cell, text in self.repo._entries_map(draft).items() if text != ""}
        return self.repo.diff_maps(spec, old_map, new_map, column_keys=draft.resolved_column_keys)

    def get_entries_page(
        self,
        version: AssetVersion,
        *,
        offset: int,
        limit: int,
        sura: int | None = None,
        filters: EntryFilters | None = None,
    ) -> tuple[list[dict], int]:
        """One page of the template's canonical units with stored text overlaid.

        Units the version has no row for come back with empty text. Nothing is
        written: a freshly created asset shows its full unit set without any
        entry rows existing.

        When the version is a translation (non-source language), each row also
        carries ``source_text`` — the source language's latest published text for
        the same unit — as a read-only reference, same as the previous per-ayah
        editor did (see the now-superseded ``get_entries``).

        ``filters`` (the grid's column filters) narrow the whole unit set before
        the page is cut, so the returned count is the filtered total.

        A committed version that was pruned to deltas has its entries rebuilt on
        first view (see ``AssetContentRepository.ensure_entries``), so history is
        browsed and filtered exactly like the current version.

        ``version`` is the one the endpoint already resolved (see ``get_version_or_404``).
        """
        asset = version.asset
        if version.state == VersionStateChoice.PUBLISHED and not version.entries.exists():
            self.repo.ensure_entries(version)

        spec = unit_spec_for(asset)
        keys = version.resolved_column_keys
        if filters is not None:
            filters = filters.for_columns(keys)
        source_version = self._source_version(asset, version)
        units, total = spec.units_page(
            asset,
            offset=offset,
            limit=limit,
            sura=sura,
            filters=filters,
            version=version,
            source_version=source_version,
        )
        unit_ids = [unit.unit_id for unit in units]
        cells = self.repo.entry_cells(version, spec, unit_ids)
        source_cells = self.repo.entry_cells(source_version, spec, unit_ids) if source_version is not None else None
        changed_cells = self._changed_cells(asset, version, spec, cells, unit_ids)

        rows = [
            {
                "unit_type": asset.template,
                "unit_id": unit.unit_id,
                "label": unit.label,
                "reference_text": unit.reference_text,
                "sura": unit.sura,
                "aya": unit.aya,
                **cell_fields(unit.unit_id, keys, cells, source_cells),
                "order": unit.order,
                **changed_fields(unit.unit_id, keys, changed_cells),
                **group_fields(unit),
            }
            for unit in units
        ]
        return rows, total

    def _changed_cells(
        self,
        asset: Asset,
        version: AssetVersion,
        spec: UnitSpec,
        cells: Snapshot,
        unit_ids: list[int],
    ) -> set[CellKey]:
        """Cells whose draft text differs from the language's latest published
        version — what a commit would record (added, modified or removed).

        A cell missing from either side reads as empty text, so an empty draft row
        with nothing published is unchanged, and clearing published text is a
        change. Only drafts are compared; any other version reports no changes.
        """
        if version.state != VersionStateChoice.DRAFT:
            return set()
        language = version.asset_language.language if version.asset_language_id else asset.language
        head = asset.get_latest_version(language)
        published = self.repo.published_cells(head, spec, unit_ids) if head is not None else {}
        wanted = set(unit_ids)
        return {
            (unit_id, key)
            for (unit_id, key) in set(cells) | set(published)
            if unit_id in wanted and (cells.get((unit_id, key)) or "") != (published.get((unit_id, key)) or "")
        }

    def _resolve_source_cells(
        self, asset: Asset, version: AssetVersion, spec: UnitSpec, unit_ids: list[int]
    ) -> Snapshot | None:
        """The source-language cells for a translation's units.

        ``None`` when this version IS the source (nothing to overlay) or when no
        source version has been published yet — every unit's ``source_cells``
        and ``source_text`` then read ``None``.
        """
        source_version = self._source_version(asset, version)
        if source_version is None:
            return None
        return self.repo.entry_cells(source_version, spec, unit_ids)

    def _source_version(self, asset: Asset, version: AssetVersion) -> AssetVersion | None:
        """The source language's latest published version a translation reads its
        reference text from; None when ``version`` is the source or none is published."""
        lang = version.asset_language
        if lang is None or lang.is_source:
            return None
        return asset.get_latest_version(asset.language)

    def get_patch_response_context(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        changed: list[AssetVersionEntry],
        publisher_q: Q | None = None,
    ) -> PatchResponseContext:
        """What a patch response needs: the template, the patched units' full
        cells (every column, not only the ones patched), their source cells and
        which of them now differ from the published version.

        Uses the same source overlay and changed rules as ``get_entries_page``,
        resolved once for the whole patched batch rather than per row, so the
        autosave response matches what the next GET would show instead of going
        blank until the page is reloaded.
        """
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        version = self.repo.get_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found.").format(id=version_id),
                status_code=404,
            )
        spec = unit_spec_for(asset)
        unit_ids = list(dict.fromkeys(entry.unit_id for entry in changed if entry.unit_id is not None))
        keys = [column.key for column in asset.text_columns()]
        if len(keys) == 1:
            # One column: the patched entries are the units' whole rows.
            cells = {(entry.unit_id, keys[0]): entry.text for entry in changed if entry.unit_id is not None}
        else:
            cells = self.repo.entry_cells(version, spec, unit_ids)
        return PatchResponseContext(
            template=asset.template,
            column_keys=keys,
            cells=cells,
            source_cells=self._resolve_source_cells(asset, version, spec, unit_ids),
            changed_cells=self._changed_cells(asset, version, spec, cells, unit_ids),
        )

    def get_version_or_404(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Return a version belonging to the asset, or raise 404."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        version = self.repo.get_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found.").format(id=version_id),
                status_code=404,
            )
        return version

    def upsert_entries(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        rows: list[dict[str, object]],
        publisher_q: Q | None = None,
    ) -> list[AssetVersionEntry]:
        """Bulk create/update draft entries (autosave). Draft-only.

        Validates each row's unit against the template before writing:
        ``valid_unit_ids`` is bounded by the patched candidates, never the
        template's full unit set (77,431 rows for word), so this check stays
        cheap on every save regardless of template.
        """
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        spec = unit_spec_for(asset)
        columns = asset.ensure_text_columns()  # cells are written to saved columns
        keys = {column.key for column in columns}
        unknown_columns = sorted(
            {str(row["column"]) for row in rows if row.get("column") and row["column"] not in keys}
        )
        if unknown_columns:
            raise ItqanError(
                error_name="unknown_column",
                message=_("This asset has no column named {columns}.").format(columns=", ".join(unknown_columns)),
                status_code=400,
            )
        candidates = [int(row["unit_id"]) for row in rows]
        valid_ids = spec.valid_unit_ids(asset, candidates)
        unknown = [unit_id for unit_id in candidates if unit_id not in valid_ids]
        if unknown:
            raise ItqanError(
                error_name="unit_not_in_template",
                message=_("Units {units} are not part of this asset's template.").format(
                    units=", ".join(str(unit) for unit in unknown[:10])
                ),
                status_code=400,
            )
        allowed = source_group_keys(draft)
        if allowed is not None:
            outside = [unit_id for unit_id in candidates if unit_id not in allowed]
            if outside:
                raise ItqanError(
                    error_name="group_not_in_source",
                    message=_("A translation can only write text for the source language's groups."),
                    status_code=400,
                )
        changed = self.repo.upsert_entries(draft, spec, rows, columns=columns)
        logger.info(f"Draft entries upserted [version_id={draft.pk}, count={len(changed)}]")
        return changed

    def _group_draft_or_400(
        self, slug: str, category: CategoryChoice, version_id: int, publisher_q: Q | None
    ) -> tuple[Asset, AssetVersion, UnitSpec]:
        """The editable draft of a group-template asset."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        spec = unit_spec_for(asset)
        if not spec.is_group:
            raise ItqanError(
                error_name="template_not_grouped",
                message=_("Only ayah-group and word-group assets have groups."),
                status_code=400,
            )
        return asset, draft, spec

    @staticmethod
    def _source_only_error() -> ItqanError:
        return ItqanError(
            error_name="group_ranges_source_only",
            message=_("Groups are added, moved and deleted in the source language; translations follow them."),
            status_code=400,
        )

    @staticmethod
    def _group_exists_error() -> ItqanError:
        return ItqanError(
            error_name="group_exists",
            message=_("This draft already has a group with exactly this range."),
            status_code=400,
        )

    def _lock_draft(self, draft: AssetVersion) -> AssetVersion:
        """Row-lock ``draft`` and re-check it is still a draft: a commit or discard
        may have landed since it was loaded."""
        locked = AssetVersion.objects.select_for_update().filter(pk=draft.pk).first()
        if locked is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found.").format(id=draft.pk),
                status_code=404,
            )
        self._require_draft(locked)
        locked.asset = draft.asset
        return locked

    @staticmethod
    def _require_group(draft: AssetVersion, spec: UnitSpec, unit_id: int) -> None:
        if not draft.entries.filter(spec.entries_q([unit_id])).exists():
            raise ItqanError(
                error_name="group_not_found",
                message=_("This draft has no such group."),
                status_code=404,
            )

    def add_group(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        start: QuranPosition,
        end: QuranPosition,
        cells: dict[str, str],
        publisher_q: Q | None = None,
    ) -> list[AssetVersionEntry]:
        """Add a group to a source-language draft, with its first text if given.

        With no text the group is a blank row in the draft's first column, to be
        filled in the grid; committing drops it if it is still blank (a committed
        group always has text).
        """
        asset, draft, spec = self._group_draft_or_400(slug, category, version_id, publisher_q)
        if draft.asset_language_id and not draft.asset_language.is_source:
            raise self._source_only_error()
        key = spec.key_for_range(start, end)
        columns = asset.ensure_text_columns()
        unknown = sorted(set(cells) - {column.key for column in columns})
        if unknown:
            raise ItqanError(
                error_name="unknown_column",
                message=_("This asset has no column named {columns}.").format(columns=", ".join(unknown)),
                status_code=400,
            )
        rows = [{"unit_id": key, "column": column, "text": text} for column, text in cells.items() if text.strip()]
        if not rows:
            rows = [{"unit_id": key, "column": columns[0].key, "text": ""}]
        try:
            with transaction.atomic():
                locked = self._lock_draft(draft)
                if locked.entries.filter(spec.entries_q([key])).exists():
                    raise self._group_exists_error()
                changed = self.repo.upsert_entries(locked, spec, rows, columns=columns)
        except IntegrityError as exc:
            # A concurrent add of the same range won the unique constraint.
            raise self._group_exists_error() from exc
        logger.info(f"Group added [version_id={draft.pk}, unit_id={key}]")
        return changed

    def append_group(
        self, slug: str, category: CategoryChoice, version_id: int, publisher_q: Q | None = None
    ) -> list[AssetVersionEntry]:
        """Add a blank one-unit group right after the furthest unit any group of the
        draft reaches (the first ayah / word when it has none): "continue writing"."""
        asset, draft, spec = self._group_draft_or_400(slug, category, version_id, publisher_q)
        if draft.asset_language_id and not draft.asset_language.is_source:
            raise self._source_only_error()
        columns = asset.ensure_text_columns()
        try:
            with transaction.atomic():
                locked = self._lock_draft(draft)
                ends = [decode_group_key(key)[1] for key in spec.stored_ranges(locked)]
                start = max(ends) + 1 if ends else spec.first_unit_id()
                key = encode_group_key(start, start) if start is not None else 0
                if start is None or key not in spec.valid_unit_ids(asset, [key]):
                    raise range_invalid_error()
                changed = self.repo.upsert_entries(
                    locked, spec, [{"unit_id": key, "column": columns[0].key, "text": ""}], columns=columns
                )
        except IntegrityError as exc:
            raise self._group_exists_error() from exc
        logger.info(f"Group appended [version_id={draft.pk}, unit_id={key}]")
        return changed

    def extend_group(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        unit_id: int,
        *,
        by: int,
        publisher_q: Q | None = None,
    ) -> list[AssetVersionEntry]:
        """Grow (``by=1``) or shrink (``by=-1``) a group's end by one ayah / word,
        keeping its text. Ids are in mushaf order, so the next unit is id + 1,
        across ayah and surah boundaries."""
        asset, draft, spec = self._group_draft_or_400(slug, category, version_id, publisher_q)
        if draft.asset_language_id and not draft.asset_language.is_source:
            raise self._source_only_error()
        start, end = decode_group_key(unit_id)
        new_key = encode_group_key(start, end + by)
        if end + by < start or new_key not in spec.valid_unit_ids(asset, [new_key]):
            raise range_invalid_error()
        try:
            with transaction.atomic():
                locked = self._lock_draft(draft)
                self._require_group(locked, spec, unit_id)
                if locked.entries.filter(spec.entries_q([new_key])).exists():
                    raise self._group_exists_error()
                moved = self.repo.move_group_cells(locked, spec, unit_id, new_key)
        except IntegrityError as exc:
            raise self._group_exists_error() from exc
        logger.info(f"Group resized [version_id={draft.pk}, from={unit_id}, to={new_key}]")
        return moved

    def move_group(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        unit_id: int,
        *,
        start: QuranPosition,
        end: QuranPosition,
        publisher_q: Q | None = None,
    ) -> list[AssetVersionEntry]:
        """Give a source-language draft's group a new range, keeping its text in every column."""
        _asset, draft, spec = self._group_draft_or_400(slug, category, version_id, publisher_q)
        if draft.asset_language_id and not draft.asset_language.is_source:
            raise self._source_only_error()
        new_key = spec.key_for_range(start, end)
        try:
            with transaction.atomic():
                locked = self._lock_draft(draft)
                self._require_group(locked, spec, unit_id)
                if new_key == unit_id:
                    return list(locked.entries.filter(spec.entries_q([unit_id])))
                if locked.entries.filter(spec.entries_q([new_key])).exists():
                    raise self._group_exists_error()
                moved = self.repo.move_group_cells(locked, spec, unit_id, new_key)
        except IntegrityError as exc:
            raise self._group_exists_error() from exc
        logger.info(f"Group moved [version_id={draft.pk}, from={unit_id}, to={new_key}]")
        return moved

    def delete_group(
        self, slug: str, category: CategoryChoice, version_id: int, unit_id: int, publisher_q: Q | None = None
    ) -> None:
        """Delete a group's cells from a draft. A translated language may only
        delete a group its source no longer has (an orphan)."""
        _asset, draft, spec = self._group_draft_or_400(slug, category, version_id, publisher_q)
        with transaction.atomic():
            locked = self._lock_draft(draft)
            self._require_group(locked, spec, unit_id)
            allowed = source_group_keys(locked)
            if allowed is not None and unit_id in allowed:
                raise self._source_only_error()
            self.repo.delete_group_cells(locked, spec, unit_id)
        logger.info(f"Group deleted [version_id={draft.pk}, unit_id={unit_id}]")

    def _forbid_orphaned_groups(self, version: AssetVersion, snapshot: Snapshot) -> None:
        """A translated language may not commit (or restore) text for ranges its source no longer has."""
        allowed = source_group_keys(version)
        if allowed is None:
            return
        spec = unit_spec_for(version.asset)
        orphans = sorted(unit_id for (unit_id, _key), text in snapshot.items() if text and unit_id not in allowed)
        if not orphans:
            return
        units = self.repo._units_by_id(spec, list(dict.fromkeys(orphans)))
        labels = [group_label(*units[unit_id]) for unit_id in dict.fromkeys(orphans) if unit_id in units]
        shown = ", ".join(labels[:10]) + (" …" if len(labels) > 10 else "")
        raise ItqanError(
            error_name="orphaned_groups",
            message=_("Move or delete the text of groups the source no longer has: {groups}.").format(groups=shown),
            status_code=400,
            extra={"groups": labels},
        )

    def import_file_into_version(self, version: AssetVersion, raw: bytes) -> int:
        """Parse an uploaded content file and replace the version's entries.

        Returns the number of entries created. Raises ``ItqanError`` (400) if the
        file cannot be parsed.
        """
        spec = unit_spec_for(version.asset)
        try:
            parsed = parse_content_file(raw, spec, version.asset, allowed_unit_ids=source_group_keys(version))
        except AssetContentMissingColumnsError as exc:
            raise missing_columns_error(exc) from exc
        except AssetContentParseError as exc:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("Could not parse the uploaded content file: {reason}").format(reason=str(exc)),
                status_code=400,
            ) from exc
        count = self.repo.replace_entries_from_parsed(version, spec, parsed)
        logger.info(f"Imported content file into version [version_id={version.pk}, entries={count}]")
        return count

    def publish_draft(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        summary_en: str = "",
        summary_ar: str = "",
        label_en: str | None = None,
        label_ar: str | None = None,
        version_number: str | None = None,
        bump: VersionBump = "minor",
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Commit a draft as the latest version with a required message — its
        summary, in English and/or Arabic (at least one). Consumers do not see it until it is approved
        and published (``set_published_version``), so nobody is notified here.

        Committing issues the draft's version number: ``version_number`` starts the
        language's sequence when it has no versions yet, otherwise the latest number
        is bumped by ``bump``. ``label_en`` / ``label_ar`` (when given) replace the
        draft's name in that language."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        if not draft.content_edited:
            raise ItqanError(
                error_name="no_changes_to_publish",
                message=_("There are no changes to publish."),
                status_code=400,
            )
        if not (summary_en.strip() or summary_ar.strip()):
            raise ItqanError(
                error_name="commit_message_required",
                message=_("A commit message is required."),
                status_code=400,
            )
        draft.summary_en = summary_en.strip()
        draft.summary_ar = summary_ar.strip()
        if label_en is not None:
            draft.label_en = label_en.strip()
        if label_ar is not None:
            draft.label_ar = label_ar.strip()
        with transaction.atomic():
            # Locked before the check, so a concurrent column reorder can't land between them.
            self.repo.lock_asset(asset)
            # Under the asset lock: a source commit can't move a group between the check and this commit.
            self._forbid_orphaned_groups(draft, self.repo._entries_map(draft))
            forbid_minor_after_column_reorder(asset, draft.asset_language.language, bump)
            draft.name = issue_version_number(asset, draft.asset_language.language, start=version_number, bump=bump)
            published = self.repo.publish_draft(draft)
        logger.info(f"Draft committed [version_id={published.pk}, asset_id={asset.pk}, name={published.name}]")
        return published

    def discard_draft(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ) -> None:
        """Delete a draft version and its entries (discard unsaved edits)."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        self.repo.delete_version(draft)
        logger.info(f"Draft discarded [version_id={version_id}, asset_id={asset.pk}]")

    def restore_version(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        bump: VersionBump = "minor",
        created_by_id: int | None = None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Restore a committed version's content as a new version, making it the
        latest one (the head) for its language. Like any commit, it is reviewed
        and published separately, and gets the next version number (by ``bump``)."""
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        if version.state != VersionStateChoice.PUBLISHED:
            raise ItqanError(
                error_name="version_not_restorable",
                message=_("Only published versions can be restored."),
                status_code=400,
            )
        language = version.asset_language.language if version.asset_language_id else version.asset.language
        with transaction.atomic():
            self.repo.lock_asset(version.asset)
            forbid_minor_after_column_reorder(version.asset, language, bump)
            self._forbid_orphaned_groups(version, self.repo.reconstruct_entries(version))
            name = issue_version_number(version.asset, language, bump=bump)
            restored = self.repo.restore_version(version, name=name, created_by_id=created_by_id)
        logger.info(f"Version restored [source_version_id={version.pk}, new_version_id={restored.pk}]")
        return restored

    def set_published_version(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        reason: str = "",
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Make a committed version the one consumers see for its language
        (translations / tafsirs: only once fully approved). Any such version may
        be published, including an older one (a rollback), which needs a
        ``reason``: the itqan CLI shows it to projects still locked to a version
        rolled back past. Re-publishing the current version is a no-op."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        with transaction.atomic():
            # Same lock as a file replacement or deletion (lock_version_for_content_change):
            # the approval checked here is the content that gets published.
            version = (
                AssetVersion.objects.select_related("asset_language", "asset")
                .select_for_update(of=("self",))
                .get(pk=version.pk)
            )
            return self._publish_locked(asset, version, reason=reason.strip())

    def publish_new_version(self, asset: Asset, version: AssetVersion) -> AssetVersion:
        """Publish a version just created (a mushaf / font upload with "publish
        now", or the first version created with its asset). Never a rollback."""
        with transaction.atomic():
            version = (
                AssetVersion.objects.select_related("asset_language", "asset")
                .select_for_update(of=("self",))
                .get(pk=version.pk)
            )
            return self._publish_locked(asset, version)

    def _publish_locked(self, asset: Asset, version: AssetVersion, *, reason: str = "") -> AssetVersion:
        """``set_published_version`` once ``version``'s row is locked."""
        if version.state != VersionStateChoice.PUBLISHED:
            raise ItqanError(
                error_name="version_not_publishable",
                message=_("Only committed versions can be published."),
                status_code=400,
            )
        if version.removed_at is not None:
            raise ItqanError(
                error_name="version_removed",
                message=_("This version was removed by an Itqan admin and can't be published."),
                status_code=400,
            )
        language = version.resolved_language
        pending = 0
        if asset.category in REVIEWED_CATEGORIES:
            pending = AssetReviewRepository().pending_cells_by_version(asset, language).get(version.pk, 0)
        if pending:
            raise ItqanError(
                error_name="version_not_approved",
                message=_("This version has {count} change(s) that are not approved yet.").format(count=pending),
                status_code=400,
            )
        rendition = version.asset_language or asset.get_or_create_source_language()
        if rendition.published_version_id == version.pk:
            return version
        previous = rendition.published_version
        previously_published_id = rendition.published_version_id
        is_rollback = version.publishing_rolls_back(previous)
        if is_rollback and not reason:
            raise ItqanError(
                error_name="rollback_reason_required",
                message=_(
                    "Give a reason for going back to an earlier version. Developers still using a newer "
                    "version see it in the itqan CLI."
                ),
                status_code=400,
            )
        self.repo.set_published_version(
            rendition, version, rolled_back_from=previous if is_rollback else None, reason=reason
        )
        logger.info(
            f"Version published [version_id={version.pk}, asset_id={asset.pk}, language={language}, "
            f"previous_version_id={previously_published_id}]"
        )
        if previously_published_id is not None:
            transaction.on_commit(lambda: notify_asset_version_created.delay(version.pk))
        transaction.on_commit(lambda: dispatch_dependabot_updates_for_version.delay(version.pk))
        return version
