"""Data-access layer for per-ayah asset content editing (drafts + entries).

Shared by translations and tafsirs; both edit the same
``AssetVersion`` / ``AssetVersionEntry`` tables.
"""

from __future__ import annotations

import csv
import io
import logging
import re

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import QuerySet

from apps.content.models import Asset, AssetVersion, AssetVersionEntry, VersionStateChoice
from apps.content.services.asset_content_import import ParsedEntry
from apps.quran.models import Ayah

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

    def get_draft(self, asset: Asset) -> AssetVersion | None:
        return self.asset_version_model.objects.filter(asset=asset, state=VersionStateChoice.DRAFT).first()

    def get_version(self, asset: Asset, version_id: int) -> AssetVersion | None:
        return self.asset_version_model.objects.filter(asset=asset, id=version_id).first()

    def get_entries(self, version: AssetVersion) -> QuerySet[AssetVersionEntry]:
        return version.entries.select_related("ayah", "ayah__sura").order_by("order", "ayah_id")

    @transaction.atomic
    def create_draft_seeded_from(
        self,
        asset: Asset,
        source_version: AssetVersion | None,
        *,
        name: str,
        summary: str,
        created_by_id: int | None,
    ) -> AssetVersion:
        """Create a draft version, copying entries from ``source_version`` if given."""
        draft = self.asset_version_model.objects.create(
            asset=asset,
            name=name,
            summary=summary,
            state=VersionStateChoice.DRAFT,
            created_by_id=created_by_id,
        )
        if source_version is not None:
            copies = [
                AssetVersionEntry(
                    version=draft,
                    ayah_id=entry.ayah_id,
                    text=entry.text,
                    footnotes=entry.footnotes,
                    order=entry.order,
                )
                for entry in source_version.entries.all().iterator()
            ]
            if copies:
                AssetVersionEntry.objects.bulk_create(copies, batch_size=1000)
        return draft

    @transaction.atomic
    def replace_entries_from_parsed(self, version: AssetVersion, parsed: list[ParsedEntry]) -> int:
        """Replace a version's entries with parsed per-ayah rows. Returns count."""
        ayah_index = self._ayah_id_by_sura_aya()
        logger.info(
            f"replace_entries_from_parsed: deleting existing entries [version_id={version.pk}, ayah_index={ayah_index}]"
        )
        version.entries.all().delete()
        rows: list[AssetVersionEntry] = []
        for parsed_entry in parsed:
            ayah_id = ayah_index.get((parsed_entry.sura, parsed_entry.aya))
            if ayah_id is None:
                continue
            rows.append(
                AssetVersionEntry(
                    version=version,
                    ayah_id=ayah_id,
                    text=parsed_entry.text,
                    footnotes=parsed_entry.footnotes,
                    order=ayah_id,
                )
            )
        logger.info(f"replace_entries_from_parsed: creating new entries [version_id={version.pk}, rows={len(rows)}]")
        if rows:
            AssetVersionEntry.objects.bulk_create(rows, batch_size=1000)
        return len(rows)

    @transaction.atomic
    def upsert_entries(self, version: AssetVersion, rows: list[dict[str, object]]) -> list[AssetVersionEntry]:
        """Create or update draft entries keyed by ayah id. Returns changed rows."""
        ayah_ids = [int(row["ayah_id"]) for row in rows]
        existing = {entry.ayah_id: entry for entry in version.entries.filter(ayah_id__in=ayah_ids)}
        to_create: list[AssetVersionEntry] = []
        to_update: list[AssetVersionEntry] = []
        changed: list[AssetVersionEntry] = []

        for row in rows:
            ayah_id = int(row["ayah_id"])
            text = str(row.get("text", "") or "")
            footnotes = str(row.get("footnotes", "") or "")
            entry = existing.get(ayah_id)
            if entry is None:
                entry = AssetVersionEntry(
                    version=version,
                    ayah_id=ayah_id,
                    text=text,
                    footnotes=footnotes,
                    order=ayah_id,
                )
                to_create.append(entry)
            else:
                entry.text = text
                entry.footnotes = footnotes
                to_update.append(entry)
            changed.append(entry)

        if to_create:
            AssetVersionEntry.objects.bulk_create(to_create, batch_size=1000)
        if to_update:
            AssetVersionEntry.objects.bulk_update(to_update, ["text", "footnotes"], batch_size=1000)
        # Mark the draft as edited so an unchanged draft can't be published.
        if changed and not version.content_edited:
            version.content_edited = True
            version.save(update_fields=["content_edited", "updated_at"])
        return changed

    def entries_to_csv_bytes(self, version: AssetVersion) -> bytes:
        """Serialize a version's per-ayah entries to CSV (sura,aya,text,footnotes)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["sura", "aya", "text", "footnotes"])
        for entry in version.entries.select_related("ayah").order_by("order", "ayah_id").iterator():
            writer.writerow([entry.ayah.sura_id, entry.ayah.number_in_sura, entry.text, entry.footnotes])
        return buffer.getvalue().encode("utf-8")

    @transaction.atomic
    def publish_draft(self, draft: AssetVersion) -> AssetVersion:
        """Flip a draft to published so newest-wins makes it the latest version.

        Also materializes a downloadable CSV file from the per-ayah entries (when
        the version has no uploaded file), so consumer download paths — the
        gallery, developers/tenant APIs — work for grid-edited versions.
        """
        draft.state = VersionStateChoice.PUBLISHED
        # Persist name/summary too: the service may have set them from the publish
        # payload, and they must be written (not just held in memory).
        update_fields = ["state", "name", "summary", "updated_at"]
        if not draft.file_url and draft.entries.exists():
            content = self.entries_to_csv_bytes(draft)
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
        return draft

    def backfill_file_from_entries(self, version: AssetVersion) -> bool:
        """Generate a CSV file for a published version that has entries but no
        file. Returns True if a file was written."""
        if version.file_url or not version.entries.exists():
            return False
        content = self.entries_to_csv_bytes(version)
        filename = f"{version.asset.slug}-{version.name}.csv".replace(" ", "_")
        version.file_url.save(filename, ContentFile(content), save=False)
        version.size_bytes = len(content)
        version.save(update_fields=["file_url", "size_bytes", "updated_at"])
        return True

    def delete_version(self, version: AssetVersion) -> None:
        version.delete()
