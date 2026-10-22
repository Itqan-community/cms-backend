"""Business rules for the text columns of translation / tafsir assets.

A column's key is what files and APIs carry, so once a committed version
contains it, the key is frozen and the column can't be deleted — that would
change a file developers may already have installed. Labels are display-only
and may change at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from django.core.cache import cache
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from apps.content.columns import csv_header, validate_column_key
from apps.content.models import REVIEWED_CATEGORIES, Asset, AssetColumn, AssetVersion, StatusChoice
from apps.content.repositories.asset_columns import AssetColumnRepository
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

PREVIEW_ROWS = 3
# A served version's content can't change while it is served (see
# `forbid_published_version_change`); its `updated_at` in the key covers a later replacement.
_PREVIEW_ROWS_CACHE_TTL = 24 * 60 * 60


@dataclass(frozen=True)
class ColumnInfo:
    key: str
    label_en: str
    label_ar: str


@dataclass(frozen=True)
class VersionStructure:
    """A text version's file layout: its template, CSV header and text columns."""

    template: str
    header: list[str]
    columns: list[ColumnInfo]


@dataclass(frozen=True)
class FileStructurePreview:
    structure: VersionStructure
    rows: list[list[str]]


def version_structure(version: AssetVersion, columns: list[AssetColumn] | None = None) -> VersionStructure:
    """``version``'s layout: its own column keys, labelled with the asset's current labels.

    ``columns`` (the asset's columns) can be passed when already loaded.
    """
    by_key = {column.key: column for column in (columns if columns is not None else version.asset.text_columns())}
    keys = version.resolved_column_keys
    return VersionStructure(
        template=version.asset.template,
        header=csv_header(version.asset.template, keys),
        columns=[
            ColumnInfo(
                key=key,
                label_en=(by_key[key].label_en or "") if key in by_key else "",
                label_ar=(by_key[key].label_ar or "") if key in by_key else "",
            )
            for key in keys
        ],
    )


class AssetColumnService:
    def __init__(self, repo: AssetColumnRepository | None = None) -> None:
        self.repo = repo or AssetColumnRepository()

    def list_columns(self, asset: Asset) -> list[AssetColumn]:
        return asset.text_columns()

    def get_column_or_404(self, asset: Asset, key: str) -> AssetColumn:
        asset.ensure_text_columns()  # an asset with no columns yet still has its default one
        column = self.repo.get(asset, key)
        if column is None:
            raise ItqanError(
                error_name="column_not_found",
                message=_("Column {key} not found.").format(key=key),
                status_code=404,
            )
        return column

    def is_committed(self, column: AssetColumn) -> bool:
        """Whether a committed version contains ``column`` (its key is then frozen)."""
        return column.key in self.repo.committed_keys(column.asset)

    def committed_keys(self, asset: Asset) -> set[str]:
        return self.repo.committed_keys(asset)

    def _require_free_key(self, asset: Asset, key: str, *, exclude_pk: int | None = None) -> None:
        validate_column_key(key)
        if self.repo.key_exists(asset, key, exclude_pk=exclude_pk):
            raise ItqanError(
                error_name="column_key_taken",
                message=_("This asset already has a column with the key {key}.").format(key=key),
                status_code=400,
            )

    @staticmethod
    def _committed_error() -> ItqanError:
        return ItqanError(
            error_name="column_committed",
            message=_("This column is part of a committed version, so it can't be renamed or deleted."),
            status_code=400,
        )

    @transaction.atomic
    def create_column(self, asset: Asset, *, key: str, label_en: str = "", label_ar: str = "") -> AssetColumn:
        asset = self.repo.lock_asset(asset)
        asset.ensure_text_columns()  # save the default column so the new one comes after it
        self._require_free_key(asset, key)
        column = self.repo.create(
            asset, key=key, label_en=label_en.strip(), label_ar=label_ar.strip(), order=self.repo.next_order(asset)
        )
        logger.info(f"Asset column created [asset_id={asset.pk}, key={key}]")
        return column

    @transaction.atomic
    def update_column(
        self,
        column: AssetColumn,
        *,
        key: str | None = None,
        label_en: str | None = None,
        label_ar: str | None = None,
    ) -> AssetColumn:
        self.repo.lock_asset(column.asset)
        fields: dict[str, str] = {}
        if key is not None and key != column.key:
            if self.is_committed(column):
                raise self._committed_error()
            self._require_free_key(column.asset, key, exclude_pk=column.pk)
            fields["key"] = key
        if label_en is not None:
            fields["label_en"] = label_en.strip()
        if label_ar is not None:
            fields["label_ar"] = label_ar.strip()
        if not fields:
            return column
        updated = self.repo.update(column, **fields)
        logger.info(f"Asset column updated [asset_id={column.asset_id}, key={updated.key}, fields={sorted(fields)}]")
        return updated

    @transaction.atomic
    def reorder_columns(self, asset: Asset, keys: list[str]) -> list[AssetColumn]:
        asset = self.repo.lock_asset(asset)
        columns = asset.ensure_text_columns()
        by_key = {column.key: column for column in columns}
        if len(keys) != len(set(keys)) or set(keys) != set(by_key):
            raise ItqanError(
                error_name="column_order_mismatch",
                message=_("The new order must list every column of the asset exactly once."),
                status_code=400,
            )
        ordered = [by_key[key] for key in keys]
        self.repo.set_orders(ordered)
        logger.info(f"Asset columns reordered [asset_id={asset.pk}, keys={keys}]")
        return ordered

    @transaction.atomic
    def delete_column(self, column: AssetColumn) -> None:
        asset = self.repo.lock_asset(column.asset)
        if len(asset.text_columns()) <= 1:
            raise ItqanError(
                error_name="column_last",
                message=_("An asset needs at least one column."),
                status_code=400,
            )
        if self.is_committed(column):
            raise self._committed_error()
        # Only drafts can hold cells of an uncommitted column; they go with it.
        self.repo.delete(column)
        logger.info(f"Asset column deleted [asset_id={asset.pk}, key={column.key}]")


class FileStructureService:
    """What the gallery shows about a text asset's download: format, columns, first rows."""

    def __init__(self, repo: AssetColumnRepository | None = None) -> None:
        self.repo = repo or AssetColumnRepository()

    @staticmethod
    def _unavailable() -> ItqanError:
        return ItqanError(
            error_name="file_structure_unavailable",
            message=_("This asset has no file structure to show in this language."),
            status_code=404,
        )

    def preview(self, asset: Asset, language: str | None) -> FileStructurePreview:
        """The published version's structure and up to ``PREVIEW_ROWS`` rows.

        Only for a READY translation / tafsir whose rendition consumers may see.
        No access grant is needed: the rows are a short sample, like public samples.
        """
        if asset.category not in REVIEWED_CATEGORIES or asset.status != StatusChoice.READY:
            raise self._unavailable()
        rendition = self.repo.consumer_rendition(asset, language or asset.language)
        if rendition is None:
            raise self._unavailable()
        version = rendition.published_version
        version.asset = asset
        structure = version_structure(version)
        keys = [column.key for column in structure.columns]
        cache_key = f"content:file-structure-rows:{version.pk}:{version.updated_at.timestamp()}:{','.join(keys)}"
        rows = cache.get(cache_key)
        if rows is None:
            rows = self._rows(asset, version, keys)
            cache.set(cache_key, rows, _PREVIEW_ROWS_CACHE_TTL)
        return FileStructurePreview(structure=structure, rows=rows)

    def _rows(self, asset: Asset, version: AssetVersion, keys: list[str]) -> list[list[str]]:
        unit_ids = self.repo.first_units_with_text(version, PREVIEW_ROWS, columns=len(keys))
        if unit_ids:
            cells = self.repo.cells_for_units(version, unit_ids)
        else:
            # A rolled-back commit may keep only its deltas: rebuild it.
            cells = self.repo.rebuilt_cells(version)
            unit_ids = sorted({unit_id for (unit_id, _), text in cells.items() if text})[:PREVIEW_ROWS]
        if not unit_ids:
            return []
        units = self.repo.unit_header_values(asset.template, unit_ids)
        return [[*units[unit_id], *(cells.get((unit_id, key), "") for key in keys)] for unit_id in unit_ids]
