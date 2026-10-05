"""Parse uploaded content files into rows keyed to an asset's template unit.

Supported ayah shapes (both are the QuranEnc CSV export shapes present in the
project's sample data):

* Translation CSV: an optional multi-line comment/preamble row, then a header
  row ``id,sura,aya,translation`` followed by one row per ayah.
* Tafsir CSV (Arabic QuranEnc): a header row that includes
  ``رقم السورة`` (sura number), ``رقم الآية`` (ayah number) and ``المحتوى``
  (content), plus import-only metadata columns.

Every template is header-driven, so each tolerates column reordering without a
per-category branch at the call site. Which columns are recognised depends on
the asset's template (``UnitSpec``):

* surah — a ``sura`` column + text.
* ayah — ``sura`` + ``aya`` + text (unchanged from the original ayah-only
  parser).
* word — either a global ``word_id`` column, or the ``sura``/``aya``/``word``
  (position-in-ayah) triple, plus text. ``word_id`` takes precedence when
  present.
* page — a ``page`` column + text.

Every resolved row is validated against the template's real unit set
(``UnitSpec.valid_unit_ids``, which is bounded by the candidates on the page —
never the template's full unit set) before it is returned, so a surah file
claiming sura 999 or a page file claiming page 700 against a shorter mushaf
layout never reaches the database.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import io
import logging
import sys

from apps.content.models import Asset, AssetTemplateChoice
from apps.content.services.asset_templates import UnitSpec

logger = logging.getLogger(__name__)

# QuranEnc tafsir/translation rows can carry very large content cells.
csv.field_size_limit(sys.maxsize)

# Header aliases -> canonical field. Lower-cased / stripped before lookup.
_SURA_HEADERS = {"sura", "surah", "رقم السورة"}
_AYA_HEADERS = {"aya", "ayah", "رقم الآية"}
_TEXT_HEADERS = {"translation", "text", "content", "المحتوى"}
_PAGE_HEADERS = {"page", "page_no", "رقم الصفحة"}
_WORD_ID_HEADERS = {"word_id", "word_index"}
_WORD_POSITION_HEADERS = {"word", "position", "رقم الكلمة"}


@dataclass(frozen=True)
class ParsedEntry:
    """One parsed row, resolved to the canonical id of its template's unit."""

    unit_id: int
    text: str


class AssetContentParseError(Exception):
    """Raised when an uploaded content file cannot be parsed into template rows."""


class AssetContentInvalidRowsError(AssetContentParseError):
    """Strict parsing found rows whose text would be silently dropped.

    ``rows`` maps a 1-based file row number to why it was rejected, so the
    uploader can fix exactly those rows.
    """

    def __init__(self, rows: dict[int, str]) -> None:
        self.rows = dict(sorted(rows.items()))
        super().__init__(f"{len(self.rows)} invalid row(s): {self.rows}")


# Why a row's text would be dropped (see ``_RowLog``).
UNREADABLE = "unreadable"
DUPLICATE = "duplicate"
UNKNOWN_UNIT = "unknown_unit"


@dataclass
class _RowLog:
    """Where each key was read from, and the rows a lenient parse silently drops.

    Only rows that carry text are recorded as problems: a blank row hides nothing
    (downloaded templates list every unit with a blank cell).
    """

    row_of: dict[object, int] = field(default_factory=dict)
    problems: dict[int, str] = field(default_factory=dict)

    def read(self, entries: dict, key: object, text: str, row_number: int) -> None:
        """Record ``key = text`` from ``row_number``, flagging a conflicting duplicate."""
        if key in entries and entries[key] != text and (entries[key] or text):
            self.problems[row_number] = DUPLICATE
        entries[key] = text
        self.row_of[key] = row_number

    def unreadable(self, row: list[str], row_number: int) -> None:
        if any((cell or "").strip() for cell in row):
            self.problems[row_number] = UNREADABLE


def _decode(raw: bytes) -> str:
    """Decode file bytes, tolerating a UTF-8 BOM (present in the tafsir export)."""
    for encoding in ("utf-8-sig", "utf-8", "cp1256"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AssetContentParseError("Unable to decode file; expected UTF-8 text.")


def _find_header_row(rows: list[list[str]]) -> int:
    """Locate the header row, skipping any leading comment/preamble rows.

    The header is the first row that contains recognisable sura + aya columns.
    """
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & _SURA_HEADERS and normalized & _AYA_HEADERS:
            return index
    raise AssetContentParseError("No recognisable header row (expected sura/aya + text columns).")


def _column_map(header: list[str]) -> dict[str, int]:
    """Map canonical field names to their column index from the header row."""
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in _SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index
        elif key in _AYA_HEADERS and "aya" not in mapping:
            mapping["aya"] = index
        elif key in _TEXT_HEADERS and "text" not in mapping:
            mapping["text"] = index

    missing = {"sura", "aya", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_surah_header_row(rows: list[list[str]]) -> int:
    """Locate the header row for a surah-template file: a sura + text column."""
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & _SURA_HEADERS and normalized & _TEXT_HEADERS:
            return index
    raise AssetContentParseError("No recognisable header row (expected a sura + text column).")


def _surah_column_map(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in _SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index
        elif key in _TEXT_HEADERS and "text" not in mapping:
            mapping["text"] = index

    missing = {"sura", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_page_header_row(rows: list[list[str]]) -> int:
    """Locate the header row for a page-template file: a page + text column."""
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & _PAGE_HEADERS and normalized & _TEXT_HEADERS:
            return index
    raise AssetContentParseError("No recognisable header row (expected a page + text column).")


def _page_column_map(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in _PAGE_HEADERS and "page" not in mapping:
            mapping["page"] = index
        elif key in _TEXT_HEADERS and "text" not in mapping:
            mapping["text"] = index

    missing = {"page", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_word_header_row(rows: list[list[str]]) -> int:
    """Locate the header row for a word-template file.

    Accepts either a ``word_id`` column or the full ``sura``/``aya``/``word``
    triple, plus text.
    """
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        has_word_id = bool(normalized & _WORD_ID_HEADERS)
        has_triple = bool(
            (normalized & _SURA_HEADERS) and (normalized & _AYA_HEADERS) and (normalized & _WORD_POSITION_HEADERS)
        )
        if (has_word_id or has_triple) and normalized & _TEXT_HEADERS:
            return index
    raise AssetContentParseError("No recognisable header row (expected word_id, or sura + aya + word, plus text).")


def _word_column_map(header: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in _WORD_ID_HEADERS and "word_id" not in mapping:
            mapping["word_id"] = index
        elif key in _SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index
        elif key in _AYA_HEADERS and "aya" not in mapping:
            mapping["aya"] = index
        elif key in _WORD_POSITION_HEADERS and "word" not in mapping:
            mapping["word"] = index
        elif key in _TEXT_HEADERS and "text" not in mapping:
            mapping["text"] = index

    if "text" not in mapping:
        raise AssetContentParseError("Header is missing required columns: text.")
    if "word_id" not in mapping and not {"sura", "aya", "word"} <= mapping.keys():
        raise AssetContentParseError("Header is missing required columns: word_id, or sura + aya + word.")
    return mapping


def _read_rows(raw: bytes) -> list[list[str]]:
    text = _decode(raw)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise AssetContentParseError("File is empty.")
    return rows


def _parse_ayah_entries(rows: list[list[str]], log: _RowLog) -> dict[tuple[int, int], str]:
    """Parse an ayah-shaped file into {(sura, aya): text}. Unchanged from the
    original ayah-only parser: rows with a non-integer sura/aya are skipped
    (almost always stray preamble lines), and duplicate (sura, aya) pairs keep
    the last occurrence."""
    header_index = _find_header_row(rows)
    columns = _column_map(rows[header_index])

    entries: dict[tuple[int, int], str] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        max_needed = max(columns.values())
        if len(row) <= max_needed:
            log.unreadable(row, row_number)
            continue
        try:
            sura = int(row[columns["sura"]].strip())
            aya = int(row[columns["aya"]].strip())
        except (ValueError, AttributeError):
            log.unreadable(row, row_number)
            continue

        content = (row[columns["text"]] or "").strip()
        log.read(entries, (sura, aya), content, row_number)
    return entries


def _parse_surah_entries(rows: list[list[str]], log: _RowLog) -> dict[int, str]:
    header_index = _find_surah_header_row(rows)
    columns = _surah_column_map(rows[header_index])

    entries: dict[int, str] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        max_needed = max(columns.values())
        if len(row) <= max_needed:
            log.unreadable(row, row_number)
            continue
        try:
            sura = int(row[columns["sura"]].strip())
        except (ValueError, AttributeError):
            log.unreadable(row, row_number)
            continue

        content = (row[columns["text"]] or "").strip()
        log.read(entries, sura, content, row_number)
    return entries


def _parse_page_entries(rows: list[list[str]], log: _RowLog) -> dict[int, str]:
    header_index = _find_page_header_row(rows)
    columns = _page_column_map(rows[header_index])

    entries: dict[int, str] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        max_needed = max(columns.values())
        if len(row) <= max_needed:
            log.unreadable(row, row_number)
            continue
        try:
            page = int(row[columns["page"]].strip())
        except (ValueError, AttributeError):
            log.unreadable(row, row_number)
            continue

        content = (row[columns["text"]] or "").strip()
        log.read(entries, page, content, row_number)
    return entries


def _parse_word_entries(
    rows: list[list[str]], log: _RowLog
) -> tuple[dict[int, str] | dict[tuple[int, int, int], str], bool]:
    """Parse a word-shaped file. Returns (entries, used_word_id).

    When the header carries a ``word_id`` column it takes precedence and
    ``entries`` is keyed by that raw id; otherwise ``entries`` is keyed by the
    (sura, aya, word-position) triple.
    """
    header_index = _find_word_header_row(rows)
    columns = _word_column_map(rows[header_index])
    used_word_id = "word_id" in columns

    if used_word_id:
        by_word_id: dict[int, str] = {}
        for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            max_needed = max(columns.values())
            if len(row) <= max_needed:
                log.unreadable(row, row_number)
                continue
            try:
                word_id = int(row[columns["word_id"]].strip())
            except (ValueError, AttributeError):
                log.unreadable(row, row_number)
                continue
            content = (row[columns["text"]] or "").strip()
            log.read(by_word_id, word_id, content, row_number)
        return by_word_id, True

    by_triple: dict[tuple[int, int, int], str] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        max_needed = max(columns.values())
        if len(row) <= max_needed:
            log.unreadable(row, row_number)
            continue
        try:
            sura = int(row[columns["sura"]].strip())
            aya = int(row[columns["aya"]].strip())
            word = int(row[columns["word"]].strip())
        except (ValueError, AttributeError):
            log.unreadable(row, row_number)
            continue
        content = (row[columns["text"]] or "").strip()
        log.read(by_triple, (sura, aya, word), content, row_number)
    return by_triple, False


def parse_content_file(raw: bytes, spec: UnitSpec, asset: Asset, *, strict: bool = False) -> list[ParsedEntry]:
    """Parse raw file bytes into rows keyed to the asset's template unit.

    Returns entries in file order. Raises ``AssetContentParseError`` when the
    file's columns do not match the template (a surah file uploaded to a
    page-based asset is a user error, not something to guess at) or when no
    row resolves to a real, in-range unit of the template.

    Lenient by default: unreadable rows, conflicting duplicates (the last one
    wins) and rows for units that do not exist are skipped. ``strict`` (uploads,
    whose content must be exactly what gets reviewed) instead raises
    ``AssetContentInvalidRowsError`` naming every such row that carries text.
    """
    rows = _read_rows(raw)
    log = _RowLog()

    resolved: dict[object, int] = {}  # raw key -> candidate unit_id
    texts: dict[object, str] = {}  # raw key -> text

    if spec.template == AssetTemplateChoice.SURAH:
        entries = _parse_surah_entries(rows, log)
        for sura, text in entries.items():
            resolved[sura] = sura
            texts[sura] = text

    elif spec.template == AssetTemplateChoice.AYAH:
        entries = _parse_ayah_entries(rows, log)
        # Local import: the repository module imports this module at load
        # time, so importing it back at module scope here would be circular.
        # By call time both modules are fully loaded.
        from apps.content.repositories.asset_content import AssetContentRepository

        ayah_index = AssetContentRepository()._ayah_id_by_sura_aya()
        for (sura, aya), text in entries.items():
            ayah_id = ayah_index.get((sura, aya))
            if ayah_id is None:
                if text:
                    log.problems[log.row_of[(sura, aya)]] = UNKNOWN_UNIT
                continue
            resolved[(sura, aya)] = ayah_id
            texts[(sura, aya)] = text

    elif spec.template == AssetTemplateChoice.WORD:
        entries, used_word_id = _parse_word_entries(rows, log)
        if used_word_id:
            for word_id, text in entries.items():
                resolved[word_id] = word_id
                texts[word_id] = text
        else:
            from apps.content.repositories.asset_content import AssetContentRepository

            word_index = AssetContentRepository()._word_id_by_sura_aya_position()
            for triple, text in entries.items():
                word_id = word_index.get(triple)
                if word_id is None:
                    if text:
                        log.problems[log.row_of[triple]] = UNKNOWN_UNIT
                    continue
                resolved[triple] = word_id
                texts[triple] = text

    else:  # page
        entries = _parse_page_entries(rows, log)
        for page, text in entries.items():
            resolved[page] = page
            texts[page] = text

    if not resolved:
        raise AssetContentParseError(f"No {spec.template} rows found after the header.")

    valid_ids = spec.valid_unit_ids(asset, list(resolved.values()))
    for key, unit_id in resolved.items():
        if unit_id not in valid_ids and texts[key]:
            log.problems[log.row_of[key]] = UNKNOWN_UNIT
    if strict and log.problems:
        raise AssetContentInvalidRowsError(log.problems)
    # A blank cell means "no content for this unit" — downloads list every unit
    # with blanks, so re-uploading one must not create an empty entry per row.
    parsed = [
        ParsedEntry(unit_id=unit_id, text=texts[key])
        for key, unit_id in resolved.items()
        if unit_id in valid_ids and texts[key]
    ]

    if not parsed:
        raise AssetContentParseError(f"No {spec.template} rows resolved to a valid unit of this asset's template.")

    logger.info(f"Parsed content file into {len(parsed)} {spec.template} entries")
    return parsed
