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
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetVersion, AssetVersionEntry, CategoryChoice, StatusChoice, VersionStateChoice
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
from apps.content.tasks import notify_asset_version_created
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

_NOT_FOUND_ERROR = {
    CategoryChoice.TRANSLATION: "translation_not_found",
    CategoryChoice.TAFSIR: "tafsir_not_found",
}


def import_uploaded_file_into_entries(version: AssetVersion) -> None:
    """Best-effort: parse an uploaded version file into per-ayah entries.

    Called from the translation/tafsir version create/update flow so that any
    uploaded content file also populates ``AssetVersionEntry`` rows (edits then
    happen on rows, never on the file). A file that cannot be parsed is logged
    and skipped so it never breaks the existing upload path.

    Reads from the *saved* ``version.file_url`` rather than the passed-in upload
    object: by the time this runs the repository has already written the upload
    to storage, which consumes the upload stream (a large ``TemporaryUploadedFile``
    ends up at EOF / closed), so re-reading the upload directly would yield empty
    bytes. Reading the persisted file is reliable for uploads of any size.
    """
    saved = getattr(version, "file_url", None)
    if not saved:
        return
    try:
        saved.open("rb")
        try:
            raw = saved.read()
        finally:
            saved.close()
    except Exception:
        logger.warning(f"Could not read saved version file for entries [version_id={version.pk}]")
        return
    try:
        parsed = parse_content_file(raw)
    except AssetContentParseError as exc:
        logger.info(f"Uploaded file not parsed into entries [version_id={version.pk}, reason={exc}]")
        return
    entries_count = AssetContentRepository().replace_entries_from_parsed(version, parsed)
    logger.info(f"Uploaded file imported into entries [version_id={version.pk}, entries={entries_count}]")


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
        created_by_id: int | None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Return the asset's shared draft, seeding it from the latest published
        version. Creates the draft if none exists; if an existing draft predates
        the latest published version (e.g. a new version was uploaded after the
        draft was started), the stale draft is rebuilt from that newer version so
        the editor always reflects the current content."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        # Lock the asset row so concurrent editor-opens can't both create a draft
        # and violate the one-draft-per-asset constraint (which would 500).
        try:
            with transaction.atomic():
                locked_asset = Asset.objects.select_for_update().get(pk=asset.pk)
                source = locked_asset.get_latest_version()
                existing = self.repo.get_draft(locked_asset)
                if existing is not None:
                    is_stale = source is not None and source.created_at > existing.created_at
                    if not is_stale:
                        return existing
                    # A newer version exists than this draft — discard the stale
                    # draft and rebuild it below from the current latest version.
                    logger.info(
                        f"Rebuilding stale draft [draft_id={existing.pk}, asset_id={locked_asset.pk}, "
                        f"newer_version_id={source.pk}]"
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
                    name=name,
                    summary=summary,
                    created_by_id=created_by_id,
                )
        except IntegrityError:
            # A concurrent request created the draft between our checks — return it.
            existing = self.repo.get_draft(asset)
            if existing is not None:
                return existing
            raise
        logger.info(
            f"Draft version created [version_id={draft.pk}, asset_id={asset.pk}, "
            f"seeded_from={source.pk if source else None}]"
        )
        return draft

    def get_entries(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        publisher_q: Q | None = None,
    ):
        """Return a version's per-ayah entries (any state; used by the editor)."""
        version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
        return self.repo.get_entries(version)

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
        name: str | None = None,
        summary: str | None = None,
        publisher_q: Q | None = None,
    ) -> AssetVersion:
        """Publish a draft so it becomes the latest version, then notify."""
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        draft = self._get_editable_draft_or_400(asset, version_id)
        if not draft.content_edited:
            raise ItqanError(
                error_name="no_changes_to_publish",
                message=_("There are no changes to publish."),
                status_code=400,
            )
        if name is not None:
            draft.name = name
        if summary is not None:
            draft.summary = summary
        published = self.repo.publish_draft(draft)
        logger.info(f"Draft published [version_id={published.pk}, asset_id={asset.pk}]")
        notify_asset_version_created.delay(published.pk)
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
