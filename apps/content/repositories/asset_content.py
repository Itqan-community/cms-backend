"""Data-access layer for per-ayah asset content editing (drafts + entries).

Shared by translations and tafsirs; both edit the same
``AssetVersion`` / ``AssetVersionEntry`` tables.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import re

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.translation import gettext as _

from apps.content.models import (
    Asset,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    AssetVersionEntry,
    ChangeTypeChoice,
    VersionStateChoice,
)
from apps.content.services.asset_content_import import AssetContentParseError, ParsedEntry, parse_content_file
from apps.content.services.asset_templates import UnitSpec, unit_spec_for
from apps.core.ninja_utils.errors import ItqanError
from apps.quran.models import Ayah, Sura, Word

logger = logging.getLogger(__name__)


class AssetContentRepository:
    def __init__(self) -> None:
        self.asset_version_model = AssetVersion
        self.entry_model = AssetVersionEntry

    def _ayah_id_by_sura_aya(self) -> dict[tuple[int, int], int]:
        """Map (sura_id, number_in_sura) -> ayah pk for resolving parsed rows."""
        return {
            (sura_id, number): ayah_id
            for ayah_id, sura_id, number in Ayah.objects.values_list("id", "sura_id", "number_in_sura")
        }

    def _word_id_by_sura_aya_position(self) -> dict[tuple[int, int, int], int]:
        """Canonical word ids keyed by (sura, ayah-in-sura, position-in-ayah).

        Builds a 77,431-entry dict in production. Used once per import — never
        call this from a request path.
        """
        return {
            (sura_id, number_in_sura, position): word_id
            for word_id, sura_id, number_in_sura, position in Word.objects.values_list(
                "id", "sura_id", "ayah__number_in_sura", "position_in_ayah"
            )
        }

    def unique_version_name(self, asset: Asset, base_name: str) -> str:
        """Return a version name unique within the asset (versions are distinct).

        Naming is "smart": if the base name ends with a number, that number is
        incremented (``v1`` → ``v2`` → ``v3``, ``الإصدار 1`` → ``الإصدار 2``),
        continuing until the name is free. If there is no trailing number, a
        numeric suffix is appended (``Draft`` → ``Draft 2``). Stays within the
        model's ``name`` max_length.
        """
        max_length = self.asset_version_model._meta.get_field("name").max_length or 255
        existing = set(self.asset_version_model.objects.filter(asset=asset).values_list("name", flat=True))

        # The last run of digits in the name (e.g. the "1" in "v1", the "2" in "v1 (2)").
        match = re.search(r"\d+(?=\D*$)", base_name)
        if match:
            start, end = match.span()
            prefix, suffix = base_name[:start], base_name[end:]
            number = int(match.group())
            candidate = base_name
            while candidate in existing:
                number += 1
                candidate = f"{prefix}{number}{suffix}"
            return candidate[:max_length]

        # No number to bump — append " 2", " 3", …
        if base_name not in existing:
            return base_name[:max_length]
        counter = 2
        while True:
            tail = f" {counter}"
            candidate = f"{base_name[: max_length - len(tail)]}{tail}"
            if candidate not in existing:
                return candidate
            counter += 1

    def get_draft(self, asset: Asset, asset_language: AssetLanguage) -> AssetVersion | None:
        return self.asset_version_model.objects.filter(
            asset=asset, asset_language=asset_language, state=VersionStateChoice.DRAFT
        ).first()

    def get_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
        return self.asset_version_model.objects.filter(asset=asset, id=version_id).first()

    def entry_text_map(self, version: AssetVersion, spec: UnitSpec, unit_ids: list[int]) -> dict[int, str]:
        """Stored text for the given units of one version, keyed by unit id.

        Only the units on the requested page are fetched, so a word-template
        request reads at most ``limit`` rows rather than the whole version.
        """
        lookup = {f"{spec.field}__in": unit_ids}
        rows = version.entries.filter(**lookup).values_list(spec.field, "text")
        return dict(rows)

    @transaction.atomic
    def ensure_mushaf_coverage(self, draft: AssetVersion, mushaf_version: AssetVersion) -> int:
        """Add empty-text rows for any mushaf ayahs the draft doesn't cover yet.

        Keeps a translation draft showing the whole original even if it was created
        sparse (before full-mushaf seeding, via upload, or when the source had
        fewer ayahs). Existing entries — including in-progress edits — are kept.
        Returns the number of rows added.
        """
        existing_ayahs = set(draft.entries.values_list("ayah_id", flat=True))
        to_create = [
            AssetVersionEntry(version=draft, ayah_id=entry.ayah_id, text="", order=entry.order)
            for entry in mushaf_version.entries.all().order_by("order", "ayah_id").iterator()
            if entry.ayah_id not in existing_ayahs
        ]
        if to_create:
            AssetVersionEntry.objects.bulk_create(to_create, batch_size=1000)
        return len(to_create)

    @transaction.atomic
    def create_draft_seeded_from(
        self,
        asset: Asset,
        source_version: AssetVersion | None,
        *,
        asset_language: AssetLanguage,
        name: str,
        summary: str,
        created_by_id: int | None,
        mushaf_version: AssetVersion | None = None,
    ) -> AssetVersion:
        """Create a draft version and seed its entries.

        When ``mushaf_version`` is given (editing an ayah-template translation —
        the only template this overlay applies to; the service never passes it
        for surah/word/page), the draft gets one row per ayah covered by the
        source-language mushaf — so the whole original is always visible — with
        the same-language translation text (from ``source_version``) overlaid
        where it exists and blank otherwise. Any translation-only ayahs beyond
        the mushaf are preserved too.

        When ``mushaf_version`` is ``None`` (editing the source, or any
        non-ayah template), the version's own ``source_version`` entries are
        copied verbatim, keyed to whichever unit column the asset's template
        uses.
        """
        draft = self.asset_version_model.objects.create(
            asset=asset,
            asset_language=asset_language,
            name=name,
            summary=summary,
            state=VersionStateChoice.DRAFT,
            created_by_id=created_by_id,
        )
        if mushaf_version is not None:
            translation_text = (
                {entry.ayah_id: entry.text for entry in source_version.entries.all().iterator()}
                if source_version is not None
                else {}
            )
            copies: list[AssetVersionEntry] = []
            seen: set[int] = set()
            # A row for every ayah of the original, translation overlaid or blank.
            for entry in mushaf_version.entries.all().order_by("order", "ayah_id").iterator():
                copies.append(
                    AssetVersionEntry(
                        version=draft,
                        ayah_id=entry.ayah_id,
                        text=translation_text.get(entry.ayah_id, ""),
                        order=entry.order,
                    )
                )
                seen.add(entry.ayah_id)
            # Keep any translated ayahs the original mushaf doesn't cover.
            if source_version is not None:
                for entry in source_version.entries.exclude(ayah_id__in=seen).order_by("order", "ayah_id").iterator():
                    copies.append(
                        AssetVersionEntry(
                            version=draft,
                            ayah_id=entry.ayah_id,
                            text=entry.text,
                            order=entry.order,
                        )
                    )
        elif source_version is not None:
            spec = unit_spec_for(asset)
            unit_field = spec.field + ("_id" if spec.fk_field else "")
            copies = [
                AssetVersionEntry(
                    version=draft,
                    text=entry.text,
                    order=entry.order,
                    **{unit_field: entry.unit_id},
                )
                for entry in source_version.entries.all().iterator()
            ]
        else:
            copies = []
        if copies:
            AssetVersionEntry.objects.bulk_create(copies, batch_size=1000)
        return draft

    @transaction.atomic
    def replace_entries_from_parsed(self, version: AssetVersion, spec: UnitSpec, parsed: list[ParsedEntry]) -> int:
        """Replace a version's entries with parsed rows, keyed to the template's
        unit column. Returns count."""
        unit_field = spec.field + ("_id" if spec.fk_field else "")
        logger.info(f"replace_entries_from_parsed: deleting existing entries [version_id={version.pk}]")
        version.entries.all().delete()
        rows = [
            AssetVersionEntry(
                version=version,
                text=parsed_entry.text,
                order=parsed_entry.unit_id,
                **{unit_field: parsed_entry.unit_id},
            )
            for parsed_entry in parsed
        ]
        logger.info(f"replace_entries_from_parsed: creating new entries [version_id={version.pk}, rows={len(rows)}]")
        if rows:
            AssetVersionEntry.objects.bulk_create(rows, batch_size=1000)
        return len(rows)

    @transaction.atomic
    def upsert_entries(
        self, version: AssetVersion, spec: UnitSpec, rows: list[dict[str, object]]
    ) -> list[AssetVersionEntry]:
        """Create or update one entry per row, keyed to the template's unit column."""
        unit_field = spec.field + ("_id" if spec.fk_field else "")
        unit_ids = [int(row["unit_id"]) for row in rows]
        existing = {
            getattr(entry, unit_field): entry for entry in version.entries.filter(**{f"{spec.field}__in": unit_ids})
        }
        to_create: list[AssetVersionEntry] = []
        to_update: list[AssetVersionEntry] = []
        changed: list[AssetVersionEntry] = []

        for row in rows:
            unit_id = int(row["unit_id"])
            text = str(row.get("text", "") or "")
            entry = existing.get(unit_id)
            if entry is None:
                entry = AssetVersionEntry(version=version, text=text, order=unit_id, **{unit_field: unit_id})
                to_create.append(entry)
            else:
                entry.text = text
                to_update.append(entry)
            changed.append(entry)

        if to_create:
            AssetVersionEntry.objects.bulk_create(to_create, batch_size=1000)
        if to_update:
            AssetVersionEntry.objects.bulk_update(to_update, ["text"], batch_size=1000)
        # Mark the draft as edited so an unchanged draft can't be published.
        if changed and not version.content_edited:
            version.content_edited = True
            version.save(update_fields=["content_edited", "updated_at"])
        return changed

    def entries_to_csv_bytes(self, version: AssetVersion, spec: UnitSpec, *, verbose: bool = False) -> bytes:
        """Serialize a version's entries to CSV, in the template's own columns.

        Lean by default: ``sura,text`` (surah), ``surah,ayah,text`` (ayah —
        byte-identical to the columns this emitted before other templates
        existed), ``word_id,sura,aya,word,text`` (word), or ``page,text``
        (page). ``verbose`` only changes the ayah template's output — it adds
        the surah name and the Arabic ayah text (``surah,ayah,surah_name,
        ayah_text,text``) so a reviewer can check a translation/tafsir against
        the original at a glance; the other templates have no analogous
        "original text" to show, so they ignore the flag. Every lean header
        matches a column the importer recognises, so a lean export round-trips.
        """
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # `id` breaks ties within an `order` value, same as version_diff below:
        # `order` is NULL-free but not unique per version, and `ayah_id` (the
        # previous tiebreak) is NULL for three of the four templates, which
        # would make a paginated non-ayah export non-deterministic.
        entries = version.entries.order_by("order", "id")

        if spec.template == AssetTemplateChoice.SURAH:
            writer.writerow(["sura", "text"])
            for entry in entries.iterator():
                writer.writerow([entry.sura_id, entry.text])
        elif spec.template == AssetTemplateChoice.WORD:
            writer.writerow(["word_id", "sura", "aya", "word", "text"])
            for entry in entries.select_related("word", "word__ayah").iterator():
                writer.writerow(
                    [
                        entry.word_id,
                        entry.word.sura_id,
                        entry.word.ayah.number_in_sura,
                        entry.word.position_in_ayah,
                        entry.text,
                    ]
                )
        elif spec.template == AssetTemplateChoice.PAGE:
            writer.writerow(["page", "text"])
            for entry in entries.iterator():
                writer.writerow([entry.page_no, entry.text])
        else:  # ayah
            if verbose:
                writer.writerow(["surah", "ayah", "surah_name", "ayah_text", "text"])
                for entry in entries.select_related("ayah", "ayah__sura").iterator():
                    writer.writerow(
                        [
                            entry.ayah.sura_id,
                            entry.ayah.number_in_sura,
                            entry.ayah.sura.name,
                            entry.ayah.text,
                            entry.text,
                        ]
                    )
            else:
                writer.writerow(["surah", "ayah", "text"])
                for entry in entries.select_related("ayah").iterator():
                    writer.writerow([entry.ayah.sura_id, entry.ayah.number_in_sura, entry.text])
        return buffer.getvalue().encode("utf-8")

    def snapshot_to_csv_bytes(self, snapshot: dict[int, str], spec: UnitSpec, *, verbose: bool = False) -> bytes:
        """Serialize a reconstructed {unit_id: text} snapshot to CSV (for
        historical commit downloads). Same columns as ``entries_to_csv_bytes``.

        ``snapshot`` keys are canonical ids of whichever unit the asset's
        template uses — a surah id, an ayah id, a word id, or a bare page
        number — never assumed to be ayah ids, unlike the id-only lookup this
        replaced. Resolved via ``spec`` through the same bulk fetch the diff
        pipeline uses (``_units_by_id``), bounded by the snapshot's own ids
        rather than the template's full unit set.
        """
        units_by_id = self._units_by_id(spec, list(snapshot))
        rows = sorted(snapshot.items(), key=lambda kv: kv[0])
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        if spec.template == AssetTemplateChoice.SURAH:
            writer.writerow(["sura", "text"])
            for unit_id, text in rows:
                if unit_id in units_by_id:
                    writer.writerow([unit_id, text])
        elif spec.template == AssetTemplateChoice.WORD:
            writer.writerow(["word_id", "sura", "aya", "word", "text"])
            for unit_id, text in rows:
                word = units_by_id.get(unit_id)
                if word is not None:
                    writer.writerow([unit_id, word.sura_id, word.ayah.number_in_sura, word.position_in_ayah, text])
        elif spec.template == AssetTemplateChoice.PAGE:
            writer.writerow(["page", "text"])
            for unit_id, text in rows:
                writer.writerow([unit_id, text])
        else:  # ayah
            if verbose:
                writer.writerow(["surah", "ayah", "surah_name", "ayah_text", "text"])
                for unit_id, text in rows:
                    ayah = units_by_id.get(unit_id)
                    if ayah is not None:
                        writer.writerow([ayah.sura_id, ayah.number_in_sura, ayah.sura.name, ayah.text, text])
            else:
                writer.writerow(["surah", "ayah", "text"])
                for unit_id, text in rows:
                    ayah = units_by_id.get(unit_id)
                    if ayah is not None:
                        writer.writerow([ayah.sura_id, ayah.number_in_sura, text])
        return buffer.getvalue().encode("utf-8")

    def _snapshot_from_file(self, version: AssetVersion) -> dict[int, str]:
        """Reconstruct a {unit_id: text} snapshot from a legacy version's stored
        file, used when a pre-entries commit (file only, no entries/deltas) is
        restored. Returns {} when the file is missing or unparseable."""
        saved = getattr(version, "file_url", None)
        if not saved:
            return {}
        try:
            saved.open("rb")
            try:
                raw = saved.read()
            finally:
                saved.close()
        except Exception:
            logger.warning(f"Could not read version file for snapshot [version_id={version.pk}]")
            return {}
        spec = unit_spec_for(version.asset)
        try:
            parsed = parse_content_file(raw, spec, version.asset)
        except AssetContentParseError:
            logger.info(f"Version file not parseable for snapshot [version_id={version.pk}]")
            return {}
        return {entry.unit_id: entry.text for entry in parsed}

    def _entries_map(self, version: AssetVersion) -> dict[int, str]:
        """{unit_id: text} for a version's full entries."""
        return {entry.unit_id: (entry.text or "") for entry in version.entries.all()}

    def _order_map(self, version: AssetVersion) -> dict[int, int]:
        """{unit_id: order} for a version's full entries."""
        return {entry.unit_id: entry.order for entry in version.entries.all()}

    def _record_changes(self, new_version: AssetVersion, previous_head: AssetVersion | None) -> dict[str, int]:
        """Store AssetVersionChange rows for new_version's delta vs previous_head.

        Returns counts keyed 'added' / 'modified' / 'removed'. The predecessor's
        map is reconstructed so it works whether or not the head still has full
        entries. Keyed to whichever unit column the asset's template uses.
        """
        spec = unit_spec_for(new_version.asset)
        unit_field = spec.field + ("_id" if spec.fk_field else "")
        old = self.reconstruct_entries(previous_head) if previous_head is not None else {}
        new = self._entries_map(new_version)
        orders = self._order_map(new_version)
        rows: list[AssetVersionChange] = []
        counts = {"added": 0, "modified": 0, "removed": 0}
        for unit_id, new_text in new.items():
            if unit_id not in old:
                change_type = ChangeTypeChoice.ADDED
                counts["added"] += 1
            elif old[unit_id] != new_text:
                change_type = ChangeTypeChoice.MODIFIED
                counts["modified"] += 1
            else:
                continue
            rows.append(
                AssetVersionChange(
                    version=new_version,
                    change_type=change_type,
                    old_text=old.get(unit_id, ""),
                    new_text=new_text,
                    order=orders.get(unit_id, unit_id),
                    **{unit_field: unit_id},
                )
            )
        for unit_id, old_text in old.items():
            if unit_id not in new:
                rows.append(
                    AssetVersionChange(
                        version=new_version,
                        change_type=ChangeTypeChoice.REMOVED,
                        old_text=old_text,
                        new_text="",
                        order=unit_id,
                        **{unit_field: unit_id},
                    )
                )
                counts["removed"] += 1
        if rows:
            AssetVersionChange.objects.bulk_create(rows, batch_size=1000)
        return counts

    def prune_version_snapshot(self, version: AssetVersion) -> None:
        """Drop a superseded commit's full snapshot (entries + file), keeping its
        stored deltas so it can still be diffed and reconstructed."""
        version.entries.all().delete()
        if version.file_url:
            version.file_url.delete(save=False)
            version.size_bytes = 0
            version.save(update_fields=["file_url", "size_bytes", "updated_at"])

    @transaction.atomic
    def publish_draft(self, draft: AssetVersion) -> AssetVersion:
        """Flip a draft to published so newest-wins makes it the latest version.

        Records the commit's delta (AssetVersionChange) vs the previous head, then
        prunes the previous head's full snapshot (only if it carries stored deltas,
        so no content is ever lost). Also materializes a downloadable CSV from the
        entries, in the asset's template columns, so consumer download paths keep
        working.
        """
        language = draft.asset_language.language if draft.asset_language_id else draft.asset.language
        previous_head = draft.asset.get_latest_version(language)  # current published head (not this draft)
        # Empty rows come from seeding a new translation with the source ayahs;
        # drop the never-filled ones so the published version stays sparse.
        draft.entries.filter(text="").delete()
        # Record this commit's per-ayah delta before flipping/pruning. content_edited
        # only proves an edit happened, not that the draft differs from the head
        # (an editor can change text then restore it), so guard on the real delta.
        counts = self._record_changes(draft, previous_head)
        if not any(counts.values()):
            raise ItqanError(
                error_name="no_changes_to_publish",
                message=_("There are no changes to publish."),
                status_code=400,
            )
        draft.state = VersionStateChoice.PUBLISHED
        # Persist name/summary too: the service may have set them from the publish
        # payload, and they must be written (not just held in memory).
        update_fields = ["state", "name", "summary", "updated_at"]
        if not draft.file_url and draft.entries.exists():
            content = self.entries_to_csv_bytes(draft, unit_spec_for(draft.asset))
            filename = f"{draft.asset.slug}-{draft.name}.csv".replace(" ", "_")
            draft.file_url.save(filename, ContentFile(content), save=False)
            draft.size_bytes = len(content)
            update_fields += ["file_url", "size_bytes"]
        draft.save(update_fields=update_fields)

        draft.asset.file_size = draft.human_readable_size
        asset_fields = ["file_size", "updated_at"]
        if not draft.asset.format:
            draft.asset.format = "csv"
            asset_fields.append("format")
        draft.asset.save(update_fields=asset_fields)

        # Prune the superseded head to deltas — but only if it carries stored
        # changes (never drop a commit that has neither entries nor a delta).
        if previous_head is not None and previous_head.changes.exists():
            self.prune_version_snapshot(previous_head)
        return draft

    def _predecessor(self, version: AssetVersion) -> AssetVersion | None:
        """The published commit immediately before `version` in its language timeline."""
        return (
            self.asset_version_model.objects.filter(
                asset=version.asset,
                asset_language=version.asset_language,
                state=VersionStateChoice.PUBLISHED,
                created_at__lt=version.created_at,
            )
            .exclude(pk=version.pk)
            .order_by("-created_at", "-id")
            .first()
        )

    def _units_by_id(self, spec: UnitSpec, unit_ids: list[int]) -> dict[int, object]:
        """Bulk-fetch the canonical unit objects a diff needs labels for.

        Only the ids appearing in the diff are fetched — never the template's
        full unit set (77,431 rows for word). Page has no backing table, so its
        "object" is just the bare page number. Ayah joins ``sura`` up front:
        ``_change_to_dict`` only needs ``sura_id`` (already on the row, no
        join required), but ``snapshot_to_csv_bytes``'s verbose branch reads
        ``ayah.sura.name`` per row, which without this join would lazy-load
        one ``Sura`` per row instead of one query for the whole batch.
        """
        if spec.template == AssetTemplateChoice.SURAH:
            return Sura.objects.in_bulk(unit_ids)
        if spec.template == AssetTemplateChoice.AYAH:
            return Ayah.objects.select_related("sura").in_bulk(unit_ids)
        if spec.template == AssetTemplateChoice.WORD:
            return Word.objects.select_related("ayah").in_bulk(unit_ids)
        return {unit_id: unit_id for unit_id in unit_ids}

    def _change_to_dict(
        self, spec: UnitSpec, unit_id: int, unit_obj: object, change_type: str, old_text: str, new_text: str
    ) -> dict:
        """Mirrors the label format ``UnitSpec._to_row`` builds for the read path."""
        if spec.template == AssetTemplateChoice.SURAH:
            label = f"{unit_obj.id}. {unit_obj.transliterated_name}"
        elif spec.template == AssetTemplateChoice.AYAH:
            label = f"{unit_obj.sura_id}:{unit_obj.number_in_sura}"
        elif spec.template == AssetTemplateChoice.WORD:
            label = f"{unit_obj.sura_id}:{unit_obj.ayah.number_in_sura}:{unit_obj.position_in_ayah}"
        else:
            label = _("Page {number}").format(number=unit_id)
        return {
            "unit_type": spec.template,
            "unit_id": unit_id,
            "label": label,
            "change_type": str(change_type),
            "old_text": old_text,
            "new_text": new_text,
        }

    @staticmethod
    def _review_fields(change: AssetVersionChange) -> dict:
        """The reviewer's outcome for a stored change; absent review = unreviewed."""
        review = getattr(change, "review", None)
        if review is None:
            return {}
        return {
            "review_state": review.state,
            "review_comment": review.comment,
            "reviewed_by": review.reviewed_by.name if review.reviewed_by_id else None,
            "reviewed_at": review.reviewed_at,
        }

    def diff_maps(self, spec: UnitSpec, old_map: dict[int, str], new_map: dict[int, str]) -> list[dict]:
        """Diff two {unit_id: text} snapshots into ordered change dicts."""
        unit_ids = sorted(set(old_map) | set(new_map))
        units_by_id = self._units_by_id(spec, unit_ids)
        out: list[dict] = []
        for unit_id in unit_ids:
            unit_obj = units_by_id.get(unit_id)
            if unit_obj is None:
                continue
            in_old, in_new = unit_id in old_map, unit_id in new_map
            if in_new and not in_old:
                out.append(self._change_to_dict(spec, unit_id, unit_obj, ChangeTypeChoice.ADDED, "", new_map[unit_id]))
            elif in_old and not in_new:
                out.append(
                    self._change_to_dict(spec, unit_id, unit_obj, ChangeTypeChoice.REMOVED, old_map[unit_id], "")
                )
            elif old_map.get(unit_id) != new_map.get(unit_id):
                out.append(
                    self._change_to_dict(
                        spec, unit_id, unit_obj, ChangeTypeChoice.MODIFIED, old_map[unit_id], new_map[unit_id]
                    )
                )
        return out

    def version_diff(self, version: AssetVersion) -> list[dict]:
        """A commit's diff: stored change rows if present, else computed from
        this commit's snapshot vs its predecessor's (legacy commits)."""
        spec = unit_spec_for(version.asset)
        # `id` breaks ties within an `order` value: `order` is NULL-free but not
        # unique per version, and this endpoint is paginated, so an unstable tie
        # order would let rows repeat or vanish across page boundaries.
        stored = list(
            version.changes.select_related("sura", "ayah", "word__ayah", "review__reviewed_by").order_by("order", "id")
        )
        if stored:
            return [
                {
                    **self._change_to_dict(
                        spec, c.unit_id, getattr(c, spec.field), c.change_type, c.old_text, c.new_text
                    ),
                    **self._review_fields(c),
                }
                for c in stored
            ]
        predecessor = self._predecessor(version)
        old_map = self.reconstruct_entries(predecessor) if predecessor is not None else {}
        return self.diff_maps(spec, old_map, self.reconstruct_entries(version))

    def reconstruct_entries(self, version: AssetVersion) -> dict[int, str]:
        """Full {unit_id: text} at this commit.

        Uses the version's own entries when present (head or a legacy commit);
        otherwise folds snapshots + deltas up to this commit for its
        (asset, language) timeline.
        """
        direct = self._entries_map(version)
        if direct:
            return direct
        timeline = (
            self.asset_version_model.objects.filter(
                asset=version.asset,
                asset_language=version.asset_language,
                state=VersionStateChoice.PUBLISHED,
                created_at__lte=version.created_at,
            )
            .order_by("created_at", "id")
            .prefetch_related("entries", "changes")
        )
        state: dict[int, str] = {}
        for commit in timeline:
            entry_map = {entry.unit_id: (entry.text or "") for entry in commit.entries.all()}
            if entry_map:
                state = entry_map  # snapshot anchor (legacy commit or head)
                continue
            for change in commit.changes.all():
                if change.change_type == ChangeTypeChoice.REMOVED:
                    state.pop(change.unit_id, None)
                else:
                    state[change.unit_id] = change.new_text
        return state

    @transaction.atomic
    def restore_version(self, version: AssetVersion, *, created_by_id: int | None = None) -> AssetVersion:
        """Restore a commit's content as a new published version (the active one).

        Works whether `version` still has full entries or was pruned to deltas
        (its snapshot is reconstructed). Records the restore's delta vs the current
        head and prunes the superseded head, so a restore is a commit like any
        other. The original is left intact, so history is preserved.
        """
        asset = version.asset
        spec = unit_spec_for(asset)
        unit_field = spec.field + ("_id" if spec.fk_field else "")
        language = version.asset_language.language if version.asset_language_id else asset.language
        previous_head = asset.get_latest_version(language)  # current head before restore
        snapshot = self.reconstruct_entries(version)  # {unit_id: text}
        order_index = self._order_map(version)
        if not snapshot and version.file_url:
            # Legacy file-only commit (pre-entries): parse its stored file so the
            # restore materializes real entries + a delta, like any other commit.
            # `_snapshot_from_file` resolves through this asset's own template
            # spec, so `unit_id` already matches what `copies` below writes via
            # `**{unit_field: unit_id}`. In practice every pre-entries legacy
            # file belongs to an ayah-template asset, since templates postdate
            # the entries system, but the resolution itself is template-generic.
            snapshot = self._snapshot_from_file(version)
        name = self.unique_version_name(asset, version.name)
        new_version = self.asset_version_model.objects.create(
            asset=asset,
            asset_language=version.asset_language,
            name=name,
            summary=version.summary,
            state=VersionStateChoice.PUBLISHED,
            created_by_id=created_by_id,
        )
        if not snapshot and version.file_url:
            # Legacy file that could not be parsed into entries: copy it verbatim so
            # the restore preserves downloadable content (no delta to record).
            extension = os.path.splitext(version.file_url.name)[1]
            filename = f"{asset.slug}-{name}{extension}".replace(" ", "_")
            version.file_url.open("rb")
            try:
                new_version.file_url.save(filename, ContentFile(version.file_url.read()), save=False)
            finally:
                version.file_url.close()
            new_version.size_bytes = version.size_bytes
            new_version.save(update_fields=["file_url", "size_bytes"])
            return new_version

        copies = [
            AssetVersionEntry(
                version=new_version, text=text, order=order_index.get(unit_id, unit_id), **{unit_field: unit_id}
            )
            for unit_id, text in snapshot.items()
            if text != ""
        ]
        if copies:
            AssetVersionEntry.objects.bulk_create(copies, batch_size=1000)
        # Record the delta vs the current head for every restore — including an
        # empty one, whose removals must be stored so later reconstruction reflects
        # the restored (empty) state instead of replaying the previous content.
        self._record_changes(new_version, previous_head)
        if copies:
            content = self.entries_to_csv_bytes(new_version, spec)
            filename = f"{asset.slug}-{name}.csv".replace(" ", "_")
            new_version.file_url.save(filename, ContentFile(content), save=False)
            new_version.size_bytes = len(content)
            new_version.save(update_fields=["file_url", "size_bytes"])
        if previous_head is not None and previous_head.changes.exists():
            self.prune_version_snapshot(previous_head)
        return new_version

    def backfill_file_from_entries(self, version: AssetVersion) -> bool:
        """Generate a CSV file for a published version that has entries but no
        file. Returns True if a file was written."""
        if version.file_url or not version.entries.exists():
            return False
        content = self.entries_to_csv_bytes(version, unit_spec_for(version.asset))
        filename = f"{version.asset.slug}-{version.name}.csv".replace(" ", "_")
        version.file_url.save(filename, ContentFile(content), save=False)
        version.size_bytes = len(content)
        version.save(update_fields=["file_url", "size_bytes", "updated_at"])
        return True

    def delete_version(self, version: AssetVersion) -> None:
        version.delete()
