"""Business rules for the public ayah text endpoint (``GET /ayahs/{ayah_key}/``).

Serves, for one ayah or a short range within a surah, the cells of several text
assets (tafsirs, translations, any tagged text asset) in one call. Only the
assets the caller names are served, each at the version consumers are served
for its source language (``AssetLanguage.published_version``).

An asset's rows are the units of its template that cover the requested ayahs:
the ayahs themselves, their words, or the ayah / word groups overlapping them.
Surah- and page-based assets have no per-ayah unit (a mushaf page has no
ayah mapping) and are rejected.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import logging
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.content.models import Asset, AssetLanguage, AssetTemplateChoice, AssetVersion, CategoryChoice
from apps.content.repositories.ayah_text import SERVED_RENDITIONS_ATTR, AyahTextRepository, EntryRow
from apps.content.services.asset_access import PublicAssetRef
from apps.content.services.asset_columns import version_structure
from apps.content.unit_keys import decode_group_key, unit_key_of
from apps.core.ninja_utils.errors import ItqanError

logger = logging.getLogger(__name__)

MAX_ASSETS_PER_REQUEST = 20
MAX_AYAHS_PER_REQUEST = 50

AYAH_BASED_TEMPLATES = frozenset(
    {
        AssetTemplateChoice.AYAH,
        AssetTemplateChoice.AYAH_GROUP,
        AssetTemplateChoice.WORD,
        AssetTemplateChoice.WORD_GROUP,
    }
)
_WORD_TEMPLATES = frozenset({AssetTemplateChoice.WORD, AssetTemplateChoice.WORD_GROUP})

# A unit's position as served: (ayah_key, word_position or None).
Position = tuple[str, int | None]


@dataclass(frozen=True)
class AyahWindow:
    """The requested ayahs (ids ``ayah_lo``..``ayah_hi``) and the words inside them."""

    surah: int
    from_ayah: int
    to_ayah: int
    ayah_lo: int
    ayah_hi: int
    ayah_numbers: dict[int, int]  # ayah_id -> number_in_surah, for every ayah in the window
    word_lo: int | None = None
    word_hi: int | None = None

    def _bounds(self, template: str) -> tuple[int, int] | None:
        if template in _WORD_TEMPLATES:
            return None if self.word_lo is None else (self.word_lo, self.word_hi)
        return self.ayah_lo, self.ayah_hi

    def unit_q(self, template: str, version_ids: list[int]) -> Q | None:
        """Entries of ``version_ids`` whose unit covers part of the window."""
        bounds = self._bounds(template)
        if bounds is None or not version_ids:
            return None
        lo, hi = bounds
        if template == AssetTemplateChoice.AYAH:
            unit = Q(ayah_id__gte=lo, ayah_id__lte=hi)
        elif template == AssetTemplateChoice.WORD:
            unit = Q(word_id__gte=lo, word_id__lte=hi)
        elif template == AssetTemplateChoice.AYAH_GROUP:
            unit = Q(from_ayah_id__lte=hi, to_ayah_id__gte=lo)
        else:
            unit = Q(from_word_id__lte=hi, to_word_id__gte=lo)
        return Q(version_id__in=version_ids) & unit

    def covers(self, template: str, unit_id: int) -> bool:
        """Python twin of :meth:`unit_q` for one unit id (rebuilt snapshots)."""
        bounds = self._bounds(template)
        if bounds is None:
            return False
        lo, hi = bounds
        if template in (AssetTemplateChoice.AYAH, AssetTemplateChoice.WORD):
            return lo <= unit_id <= hi
        start, end = decode_group_key(unit_id)
        return start <= hi and end >= lo


@dataclass(frozen=True)
class ServedAsset:
    asset: Asset
    rendition: AssetLanguage
    version: AssetVersion

    @property
    def ref(self) -> PublicAssetRef:
        return PublicAssetRef(id=self.asset.pk, slug=self.asset.slug, is_open_access=self.asset.is_open_access)


def _ayah_not_found(ayah_key: str) -> ItqanError:
    return ItqanError(
        error_name="ayah_not_found",
        message=_("Ayah {ayah_key} not found.").format(ayah_key=ayah_key),
        status_code=404,
    )


def _invalid_range() -> ItqanError:
    return ItqanError(
        error_name="invalid_ayah_range",
        message=_(
            "The range must end at or after its first ayah, within the same surah, " "and cover at most {max} ayahs."
        ).format(max=MAX_AYAHS_PER_REQUEST),
        status_code=400,
    )


def parse_ayah_key(ayah_key: str) -> tuple[int, int]:
    """``(surah, ayah)`` of a ``"surah:ayah"`` key; 404 ``ayah_not_found`` when malformed."""
    parts = ayah_key.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise _ayah_not_found(ayah_key)
    surah, ayah = int(parts[0]), int(parts[1])
    if not (1 <= surah <= 114) or ayah < 1:
        raise _ayah_not_found(ayah_key)
    return surah, ayah


def parse_asset_slugs(values: list[str] | None) -> list[str]:
    """The requested slugs in order, de-duplicated; ``?assets=`` may repeat and/or hold commas."""
    slugs: list[str] = []
    for value in values or []:
        for slug in value.split(","):
            slug = slug.strip()
            if slug and slug not in slugs:
                slugs.append(slug)
    if not slugs:
        raise ItqanError(
            error_name="assets_required",
            message=_("List the text assets to return in the assets parameter, e.g. ?assets=slug-1,slug-2."),
            status_code=400,
        )
    if len(slugs) > MAX_ASSETS_PER_REQUEST:
        raise ItqanError(
            error_name="too_many_assets",
            message=_("At most {max} assets can be requested at once.").format(max=MAX_ASSETS_PER_REQUEST),
            status_code=400,
        )
    return slugs


class AyahTextService:
    def __init__(self, repo: AyahTextRepository | None = None) -> None:
        self.repo = repo or AyahTextRepository()

    # --- request resolution ---------------------------------------------------

    def resolve_window(self, ayah_key: str, surah: int, from_ayah: int, to_ayah: int | None) -> AyahWindow:
        """The requested ayahs; 404 when the first is missing, 400 for a bad range."""
        last = from_ayah if to_ayah is None else to_ayah
        if last < from_ayah or last - from_ayah + 1 > MAX_AYAHS_PER_REQUEST:
            raise _invalid_range()
        ayahs = self.repo.get_ayahs(surah, from_ayah, last)
        if not ayahs or ayahs[0][1] != from_ayah:
            raise _ayah_not_found(ayah_key)
        if ayahs[-1][1] != last:
            raise _invalid_range()
        return AyahWindow(
            surah=surah,
            from_ayah=from_ayah,
            to_ayah=last,
            ayah_lo=ayahs[0][0],
            ayah_hi=ayahs[-1][0],
            ayah_numbers=dict(ayahs),
        )

    def resolve_assets(self, slugs: list[str]) -> list[ServedAsset]:
        """The named assets in request order, or the first rule they break:
        404 ``asset_not_found`` (unknown, off the public-API channel, not READY,
        or nothing published in its source language), 400 ``asset_not_text``,
        400 ``asset_not_ayah_based``. Each error's ``extra.assets`` names the slugs.
        """
        by_slug = {asset.slug: asset for asset in self.repo.get_public_assets(slugs)}
        not_found: list[str] = []
        not_text: list[str] = []
        not_ayah_based: list[str] = []
        served: list[ServedAsset] = []
        for slug in slugs:
            asset = by_slug.get(slug)
            if asset is None:
                not_found.append(slug)
            elif asset.category != CategoryChoice.TEXT:
                not_text.append(slug)
            elif not getattr(asset, SERVED_RENDITIONS_ATTR):
                not_found.append(slug)
            elif asset.template not in AYAH_BASED_TEMPLATES:
                not_ayah_based.append(slug)
            else:
                rendition = getattr(asset, SERVED_RENDITIONS_ATTR)[0]
                version = rendition.published_version
                # Reuse the loaded rows: column keys, labels and rebuilds read them.
                version.asset = asset
                version.asset_language = rendition
                served.append(ServedAsset(asset=asset, rendition=rendition, version=version))

        if not_found:
            raise ItqanError(
                error_name="asset_not_found",
                message=_("These assets were not found: {slugs}.").format(slugs=", ".join(not_found)),
                status_code=404,
                extra={"assets": not_found},
            )
        if not_text:
            raise ItqanError(
                error_name="asset_not_text",
                message=_("Only text assets (such as tafsirs and translations) can be requested: {slugs}.").format(
                    slugs=", ".join(not_text)
                ),
                status_code=400,
                extra={"assets": not_text},
            )
        if not_ayah_based:
            raise ItqanError(
                error_name="asset_not_ayah_based",
                message=_(
                    "These assets are not organised by ayah or word, so they can't be read per ayah: {slugs}."
                ).format(slugs=", ".join(not_ayah_based)),
                status_code=400,
                extra={"assets": not_ayah_based},
            )
        return served

    # --- content --------------------------------------------------------------

    def build_payload(self, window: AyahWindow, served: list[ServedAsset]) -> dict[str, Any]:
        """The response body: each asset's columns and the rows covering the window."""
        if any(item.asset.template in _WORD_TEMPLATES for item in served):
            words = self.repo.get_words(window.ayah_lo, window.ayah_hi)
        else:
            words = []
        if words:
            window = replace(window, word_lo=words[0][0], word_hi=words[-1][0])

        cells = self._cells(window, served)
        positions = self._positions(window, served, cells, words)
        return {
            "surah_number": window.surah,
            "from_ayah": window.from_ayah,
            "to_ayah": window.to_ayah,
            "assets": [self._asset_payload(item, cells.get(item.version.pk, {}), positions) for item in served],
        }

    def _cells(self, window: AyahWindow, served: list[ServedAsset]) -> dict[int, dict[int, dict[str, str]]]:
        """``{version_id: {unit_id: {column_key: text}}}`` for the units covering the window.

        Versions holding entries are read in one query; a published version kept
        only as deltas (a rollback target) is rebuilt and narrowed in Python.
        """
        with_entries: dict[str, list[int]] = defaultdict(list)
        rebuilt: list[ServedAsset] = []
        for item in served:
            if item.rendition.published_has_entries:
                with_entries[item.asset.template].append(item.version.pk)
            else:
                rebuilt.append(item)

        unit_qs = [q for template, ids in with_entries.items() if (q := window.unit_q(template, ids)) is not None]
        result: dict[int, dict[int, dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
        row: EntryRow
        for row in self.repo.get_entry_rows(unit_qs):
            version_id, *units, key, text = row
            result[version_id][unit_key_of(units)][key] = text

        for item in rebuilt:
            logger.info(f"Ayah text served from a rebuilt version [version_id={item.version.pk}]")
            for (unit_id, key), text in self.repo.rebuild_cells(item.version).items():
                if text and window.covers(item.asset.template, unit_id):
                    result[item.version.pk][unit_id][key] = text
        return result

    def _positions(
        self,
        window: AyahWindow,
        served: list[ServedAsset],
        cells: dict[int, dict[int, dict[str, str]]],
        words: list[tuple[int, int, int]],
    ) -> dict[str, dict[int, Position]]:
        """Served positions of every unit end in ``cells``: ``{"ayah"|"word": {id: position}}``.

        Ends inside the window are known already; a group may start or end
        outside it, and those ends are looked up (one query per kind at most).
        """
        ayah_ids: set[int] = set()
        word_ids: set[int] = set()
        for item in served:
            template = item.asset.template
            for unit_id in cells.get(item.version.pk, {}):
                ends = (
                    decode_group_key(unit_id)
                    if template
                    in (
                        AssetTemplateChoice.AYAH_GROUP,
                        AssetTemplateChoice.WORD_GROUP,
                    )
                    else (unit_id,)
                )
                (word_ids if template in _WORD_TEMPLATES else ayah_ids).update(ends)

        ayah_positions: dict[int, Position] = {
            ayah_id: (f"{window.surah}:{number}", None) for ayah_id, number in window.ayah_numbers.items()
        }
        if missing := ayah_ids - ayah_positions.keys():
            for ayah_id, (surah, number) in self.repo.get_ayah_keys(missing).items():
                ayah_positions[ayah_id] = (f"{surah}:{number}", None)

        word_positions: dict[int, Position] = {
            word_id: (ayah_positions[ayah_id][0], position) for word_id, ayah_id, position in words
        }
        if missing := word_ids - word_positions.keys():
            for word_id, (surah, number, position) in self.repo.get_word_positions(missing).items():
                word_positions[word_id] = (f"{surah}:{number}", position)
        return {"ayah": ayah_positions, "word": word_positions}

    @staticmethod
    def _asset_payload(
        item: ServedAsset, units: dict[int, dict[str, str]], positions: dict[str, dict[int, Position]]
    ) -> dict[str, Any]:
        asset, version = item.asset, item.version
        structure = version_structure(version, list(asset.columns.all()))
        keys = [column.key for column in structure.columns]
        template = asset.template
        kind = "word" if template in _WORD_TEMPLATES else "ayah"
        grouped = template in (AssetTemplateChoice.AYAH_GROUP, AssetTemplateChoice.WORD_GROUP)

        rows = []
        for unit_id in sorted(units):
            start_id, end_id = decode_group_key(unit_id) if grouped else (unit_id, unit_id)
            start, end = positions[kind].get(start_id), positions[kind].get(end_id)
            if start is None or end is None:
                continue  # a unit whose Quran row is missing: nothing to place it at
            rows.append(
                {
                    "start": {"ayah_key": start[0], "word_position": start[1]},
                    "end": {"ayah_key": end[0], "word_position": end[1]},
                    "cells": {key: units[unit_id].get(key, "") for key in keys},
                }
            )

        return {
            "slug": asset.slug,
            "name_en": asset.name_en or "",
            "name_ar": asset.name_ar or "",
            "category": asset.category,
            "tags": [tag.slug for tag in asset.tags.all()],
            "template": template,
            "language": item.rendition.language,
            "version": version.name,
            "columns": [
                {"key": column.key, "label_en": column.label_en, "label_ar": column.label_ar}
                for column in structure.columns
            ],
            "rows": rows,
        }
