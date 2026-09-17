"""Business logic for per-ayah asset content editing (translations & tafsirs).

Flow: open editor -> get-or-create a shared server-side *draft* version (seeded
from the latest published version) -> edit its entries -> either *publish* the
draft (newest-wins makes it the latest version) or *discard* it. Drafts are
excluded from every "latest / published" query (see model + Phase 0 guards), so
in-progress edits never leak to public/tenant/developers surfaces.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetVersion, AssetVersionEntry, CategoryChoice, StatusChoice, VersionStateChoice
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
from apps.content.services.asset_templates import UnitSpec, unit_spec_for
from apps.content.tasks import notify_asset_version_created
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

_NOT_FOUND_ERROR = {
    CategoryChoice.TRANSLATION: "translation_not_found",
    CategoryChoice.TAFSIR: "tafsir_not_found",
}


def import_uploaded_file_into_entries(version: AssetVersion, *, strict: bool = False) -> None:
    """Parse an uploaded version file into per-ayah entries.

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
    try:
        parsed = parse_content_file(raw)
    except AssetContentParseError as exc:
        logger.info(f"Uploaded file not parsed into entries [version_id={version.pk}, reason={exc}]")
        if strict:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("The uploaded file could not be parsed into ayah entries."),
                status_code=400,
            ) from exc
        return
    entries_count = AssetContentRepository().replace_entries_from_parsed(version, parsed)
    logger.info(f"Uploaded file imported into entries [version_id={version.pk}, entries={entries_count}]")


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
        if version.state != VersionStateChoice.DRAFT:
            raise ItqanError(
                error_name="version_not_editable",
                message=_("Only draft versions can be edited."),
                status_code=400,
            )
        return version

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
                # yet or that a previous sparse publish dropped.
                mushaf = None
                if not asset_language.is_source:
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
                # Versions carry distinct names, so a draft must not reuse the source
                # version's name verbatim (it would collide with it on save).
                base_name = source.name if source else _("Draft")
                name = self.repo.unique_version_name(locked_asset, base_name)
                summary = source.summary if source else ""
                draft = self.repo.create_draft_seeded_from(
                    locked_asset,
                    source,
                    asset_language=asset_language,
                    name=name,
                    summary=summary,
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

    def get_pending_changes(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ) -> list[dict]:
        """The uncommitted diff of a draft vs the current head — what a commit would
        record. Empty draft rows are excluded (they are dropped on commit)."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        language = draft.asset_language.language if draft.asset_language_id else asset.language
        head = draft.asset.get_latest_version(language)
        old_map = self.repo.reconstruct_entries(head) if head is not None else {}
        new_map = {ayah_id: text for ayah_id, text in self.repo._entries_map(draft).items() if text != ""}
        return self.repo.diff_maps(old_map, new_map)

    def get_entries(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ):
        """Return a version's per-ayah entries (any state; used by the editor).

        When the version is a translation (non-source language), each row is
        annotated with ``source_text`` — the source language's latest published
        text for the same ayah — so the editor can show it as a read-only
        reference beside the editable target text.
        """
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        qs = self.repo.get_entries(version)
        lang = version.asset_language
        if lang is not None and not lang.is_source:
            source_version = version.asset.get_latest_version(version.asset.language)
            if source_version is not None:
                source_text = AssetVersionEntry.objects.filter(
                    version=source_version, ayah_id=OuterRef("ayah_id")
                ).values("text")[:1]
                qs = qs.annotate(source_text=Subquery(source_text))
        return qs

    def get_entries_page(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        offset: int,
        limit: int,
        sura: int | None = None,
        publisher_q: Q | None = None,
    ) -> tuple[list[dict], int]:
        """One page of the template's canonical units with stored text overlaid.

        Units the version has no row for come back with empty text. Nothing is
        written: a freshly created asset shows its full unit set without any
        entry rows existing.

        When the version is a translation (non-source language), each row also
        carries ``source_text`` — the source language's latest published text for
        the same unit — as a read-only reference, same as the previous per-ayah
        editor did (see the now-superseded ``get_entries``).
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
        units, total = spec.units_page(asset, offset=offset, limit=limit, sura=sura)
        unit_ids = [unit.unit_id for unit in units]
        text_by_unit = self.repo.entry_text_map(version, spec, unit_ids)
        source_text_by_unit = self._resolve_source_text(asset, version, spec, unit_ids)

        rows = [
            {
                "unit_type": asset.template,
                "unit_id": unit.unit_id,
                "label": unit.label,
                "reference_text": unit.reference_text,
                "sura": unit.sura,
                "aya": unit.aya,
                "text": text_by_unit.get(unit.unit_id, ""),
                "source_text": source_text_by_unit.get(unit.unit_id),
                "order": unit.order,
            }
            for unit in units
        ]
        return rows, total

    def _resolve_source_text(
        self, asset: Asset, version: AssetVersion, spec: UnitSpec, unit_ids: list[int]
    ) -> dict[int, str]:
        """The source-language text map for a translation's units.

        Empty when this version IS the source (nothing to overlay) or when no
        source version has been published yet — in both cases every unit's
        ``source_text`` should read ``None``, which an empty map already gives
        via ``.get()``.
        """
        lang = version.asset_language
        if lang is None or lang.is_source:
            return {}
        source_version = asset.get_latest_version(asset.language)
        if source_version is None:
            return {}
        return self.repo.entry_text_map(source_version, spec, unit_ids)

    def get_patch_response_context(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        changed: list[AssetVersionEntry],
        publisher_q: Q | None = None,
    ) -> tuple[str, dict[int, str]]:
        """``(asset.template, source_text_by_unit)`` for shaping a patch response.

        Uses the same source-text overlay rule as ``get_entries_page``, resolved
        once for the whole patched batch rather than per row, so the autosave
        response matches what the next GET would show instead of going blank
        until the page is reloaded.
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
        unit_ids = [entry.unit_id for entry in changed if entry.unit_id is not None]
        source_text_by_unit = self._resolve_source_text(asset, version, spec, unit_ids)
        return asset.template, source_text_by_unit

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
        """Bulk create/update draft entries (autosave). Draft-only."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        changed = self.repo.upsert_entries(draft, rows)
        logger.info(f"Draft entries upserted [version_id={draft.pk}, count={len(changed)}]")
        return changed

    def import_file_into_version(self, version: AssetVersion, raw: bytes) -> int:
        """Parse an uploaded content file and replace the version's entries.

        Returns the number of entries created. Raises ``ItqanError`` (400) if the
        file cannot be parsed.
        """
        try:
            parsed = parse_content_file(raw)
        except AssetContentParseError as exc:
            raise ItqanError(
                error_name="content_file_unparseable",
                message=_("Could not parse the uploaded content file: {reason}").format(reason=str(exc)),
                status_code=400,
            ) from exc
        count = self.repo.replace_entries_from_parsed(version, parsed)
        logger.info(f"Imported content file into version [version_id={version.pk}, entries={count}]")
        return count

    def publish_draft(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        message: str,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Commit a draft: publish it as the latest version with a required message
        (stored as the version's description), then notify."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        if not draft.content_edited:
            raise ItqanError(
                error_name="no_changes_to_publish",
                message=_("There are no changes to publish."),
                status_code=400,
            )
        if not (message or "").strip():
            raise ItqanError(
                error_name="commit_message_required",
                message=_("A commit message is required."),
                status_code=400,
            )
        draft.summary = message.strip()
        published = self.repo.publish_draft(draft)
        logger.info(f"Draft committed [version_id={published.pk}, asset_id={asset.pk}]")
        transaction.on_commit(lambda: notify_asset_version_created.delay(published.pk))
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
        created_by_id: int | None = None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Restore a published version's content as a new version, making it the
        latest (active) one for its language."""
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        if version.state != VersionStateChoice.PUBLISHED:
            raise ItqanError(
                error_name="version_not_restorable",
                message=_("Only published versions can be restored."),
                status_code=400,
            )
        restored = self.repo.restore_version(version, created_by_id=created_by_id)
        logger.info(f"Version restored [source_version_id={version.pk}, new_version_id={restored.pk}]")
        notify_asset_version_created.delay(restored.pk)
        return restored
