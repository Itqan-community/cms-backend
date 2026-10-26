"""ORM access for the text columns of translation / tafsir assets."""

from __future__ import annotations

from django.db.models import Exists, OuterRef

from apps.content.columns import Snapshot
from apps.content.models import (
    GROUP_TEMPLATES,
    Asset,
    AssetColumn,
    AssetLanguage,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    StatusChoice,
    VersionStateChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_position, unit_spec_for_template
from apps.content.unit_keys import UNIT_VALUE_FIELDS, decode_group_key, unit_key_of, unit_q
from apps.quran.models import Ayah, Word


class AssetColumnRepository:
    def __init__(self) -> None:
        self.model = AssetColumn

    def lock_asset(self, asset: Asset) -> Asset:
        """Row-lock the asset for the rest of the transaction (serializes column edits)."""
        return Asset.objects.select_for_update().get(pk=asset.pk)

    def get(self, asset: Asset, key: str) -> AssetColumn | None:
        return self.model.objects.filter(asset=asset, key=key).first()

    def key_exists(self, asset: Asset, key: str, *, exclude_pk: int | None = None) -> bool:
        qs = self.model.objects.filter(asset=asset, key=key)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        return qs.exists()

    def next_order(self, asset: Asset) -> int:
        last = self.model.objects.filter(asset=asset).order_by("-order").values_list("order", flat=True).first()
        return 0 if last is None else last + 1

    def create(self, asset: Asset, **fields) -> AssetColumn:
        return self.model.objects.create(asset=asset, **fields)

    def update(self, column: AssetColumn, **fields) -> AssetColumn:
        for name, value in fields.items():
            setattr(column, name, value)
        update_fields = list(fields.keys())
        if "label_en" in fields or "label_ar" in fields:
            # `label` resolves from label_<active-language>; it reaches the DB only
            # when listed (see MushafLayoutRepository.update).
            update_fields.append("label")
        column.save(update_fields=[*update_fields, "updated_at"])
        return column

    def set_orders(self, columns: list[AssetColumn]) -> None:
        for position, column in enumerate(columns):
            if column.order != position:
                column.order = position
                column.save(update_fields=["order", "updated_at"])

    def delete(self, column: AssetColumn) -> None:
        column.delete()

    def committed_keys(self, asset: Asset) -> set[str]:
        """Every column key a committed version of ``asset`` contains."""
        keys: set[str] = set()
        rows = AssetVersion.objects.filter(asset=asset, state=VersionStateChoice.PUBLISHED).values_list(
            "column_keys", flat=True
        )
        for column_keys in rows:
            keys.update(column_keys or [])
        # A column with any recorded change is committed too (one EXISTS per column).
        changed = Exists(AssetVersionChange.objects.filter(column=OuterRef("pk")))
        keys.update(self.model.objects.filter(asset=asset).filter(changed).values_list("key", flat=True))
        return keys

    def consumer_rendition(self, asset: Asset, language: str) -> AssetLanguage | None:
        """``asset``'s rendition in ``language`` when consumers may see it: READY with a
        published version (which is selected alongside)."""
        return (
            AssetLanguage.objects.select_related("published_version")
            .filter(asset=asset, language=language, status=StatusChoice.READY, published_version__isnull=False)
            .first()
        )

    def first_units_with_text(self, version: AssetVersion, limit: int, *, columns: int) -> list[int]:
        """The first ``limit`` units (in display order) that have any non-blank cell.

        A unit has at most one cell per column, so the first ``limit * columns``
        non-blank cells hold those units: only those are read.
        """
        units: list[int] = []
        rows = (
            version.entries.exclude(text="")
            .order_by("order", *UNIT_VALUE_FIELDS)
            .values_list(*UNIT_VALUE_FIELDS)[: limit * max(columns, 1)]
        )
        for row in rows:
            unit_id = unit_key_of(row)
            if unit_id not in units:
                units.append(unit_id)
                if len(units) == limit:
                    break
        return units

    def cells_for_units(self, version: AssetVersion, unit_ids: list[int]) -> Snapshot:
        cells: Snapshot = {}
        for *units, key, text in version.entries.filter(unit_q(unit_ids)).values_list(
            *UNIT_VALUE_FIELDS, "column__key", "text"
        ):
            cells[(unit_key_of(units), key)] = text
        return cells

    def rebuilt_cells(self, version: AssetVersion) -> Snapshot:
        """Every cell of a commit that kept only its deltas (pruned), rebuilt without writing."""
        return AssetContentRepository().reconstruct_entries(version)

    def unit_header_values(self, template: str, unit_ids: list[int]) -> dict[int, list[str]]:
        """The unit part of each unit's CSV row, as ``csv_header`` names it (lean)."""
        if template == AssetTemplateChoice.AYAH:
            ayahs = Ayah.objects.filter(id__in=unit_ids).values_list("id", "sura_id", "number_in_sura")
            return {ayah_id: [str(sura), str(number)] for ayah_id, sura, number in ayahs}
        if template == AssetTemplateChoice.WORD:
            words = Word.objects.filter(id__in=unit_ids).values_list(
                "id", "sura_id", "ayah__number_in_sura", "position_in_ayah"
            )
            return {word_id: [str(word_id), str(sura), str(aya), str(pos)] for word_id, sura, aya, pos in words}
        if template in GROUP_TEMPLATES:
            spec = unit_spec_for_template(template)
            pairs = {unit_id: decode_group_key(unit_id) for unit_id in unit_ids}
            ends = spec.group_units({end for pair in pairs.values() for end in pair})
            return {
                unit_id: [str(part) for end in (start, stop) for part in unit_position(ends[end])]
                for unit_id, (start, stop) in pairs.items()
            }
        return {unit_id: [str(unit_id)] for unit_id in unit_ids}  # surah id / page number
