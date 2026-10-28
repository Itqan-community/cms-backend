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
* ayah_group — ``from_surah,from_ayah,to_surah,to_ayah`` + text.
* word_group — ``from_surah,from_ayah,from_word,to_surah,to_ayah,to_word`` +
  text (word positions within their ayah). Group files are always parsed
  strictly: a row repeating a range (even with the same text), naming a
  position that doesn't exist, or ending before it starts rejects the file, so
  a group tafsir is never half-imported. A verbose export's
  ``reference_text`` column is ignored.

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

from apps.content.columns import (
    AYA_HEADERS,
    PAGE_HEADERS,
    RANGE_HEADERS_BY_TEMPLATE,
    SURA_HEADERS,
    WORD_ID_HEADERS,
    WORD_POSITION_HEADERS,
)
from apps.content.models import Asset, AssetTemplateChoice
from apps.content.services.asset_templates import UnitSpec
from apps.content.unit_keys import encode_group_key

logger = logging.getLogger(__name__)

# QuranEnc tafsir/translation rows can carry very large content cells.
csv.field_size_limit(sys.maxsize)

# Header aliases -> canonical field. Lower-cased / stripped before lookup.
# Unit aliases live in ``apps.content.columns`` so column keys cannot shadow them.
_TEXT_HEADERS = {"translation", "text", "content", "المحتوى"}


@dataclass(frozen=True)
class ParsedEntry:
    """One parsed row, resolved to the canonical id of its template's unit.

    ``cells`` holds the row's non-blank text per column key.
    """

    unit_id: int
    cells: dict[str, str]


class AssetContentParseError(Exception):
    """Raised when an uploaded content file cannot be parsed into template rows."""


class AssetContentMissingColumnsError(AssetContentParseError):
    """A multi-column file lacks a header for some of the asset's columns.

    An upload replaces a whole version, so a missing column would read as every
    one of its cells removed.
    """

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"Header is missing columns: {', '.join(missing)}.")


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
RANGE_REVERSED = "range_reversed"
NOT_IN_SOURCE = "not_in_source"


@dataclass
class _RowLog:
    """Where each key was read from, and the rows a lenient parse silently drops.

    Only rows that carry text are recorded as problems: a blank row hides nothing
    (downloaded templates list every unit with a blank cell).
    """

    row_of: dict[object, int] = field(default_factory=dict)
    problems: dict[int, str] = field(default_factory=dict)

    def read(self, entries: dict, key: object, text: Cells, row_number: int) -> None:
        """Record ``key = text`` from ``row_number``, flagging a conflicting duplicate."""
        if key in entries and entries[key] != text and (any(entries[key]) or any(text)):
            self.problems[row_number] = DUPLICATE
        entries[key] = text
        self.row_of[key] = row_number

    def unreadable(self, row: list[str], row_number: int) -> None:
        if any((cell or "").strip() for cell in row):
            self.problems[row_number] = UNREADABLE


# A row's text, one cell per column key in order.
Cells = tuple[str, ...]
# Column key -> header names accepted for it (lower-cased).
TextHeaders = dict[str, set[str]]


def _text_headers(column_keys: list[str]) -> TextHeaders:
    """Which headers fill which column: a single column also takes the legacy
    text aliases (``translation``, ``content``, …); several need exact keys."""
    if len(column_keys) == 1:
        return {column_keys[0]: _TEXT_HEADERS | {column_keys[0]}}
    return {key: {key} for key in column_keys}


def _any_text_header(text_headers: TextHeaders) -> set[str]:
    return set().union(*text_headers.values())


def _text_column_map(header: list[str], text_headers: TextHeaders) -> dict[str, int]:
    """``{"text": <first text column's index>, "text:<key>": index, …}``.

    Raises ``AssetContentMissingColumnsError`` when a multi-column header lacks
    some keys; a single-column header without text is left to the caller's
    "missing required columns" error, as before columns existed.
    """
    found: dict[str, int] = {}
    for index, cell in enumerate(header):
        name = cell.strip().lower()
        for key, accepted in text_headers.items():
            if name in accepted and key not in found:
                found[key] = index
                break
    if len(text_headers) > 1:
        missing = [key for key in text_headers if key not in found]
        if missing:
            raise AssetContentMissingColumnsError(missing)
    if not found:
        return {}
    first = next(iter(text_headers))
    return {"text": found.get(first, min(found.values())), **{f"text:{key}": index for key, index in found.items()}}


def _row_cells(row: list[str], columns: dict[str, int], text_headers: TextHeaders) -> Cells:
    return tuple((row[columns[f"text:{key}"]] or "").strip() for key in text_headers)


def _decode(raw: bytes) -> str:
    """Decode file bytes, tolerating a UTF-8 BOM (present in the tafsir export)."""
    for encoding in ("utf-8-sig", "utf-8", "cp1256"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AssetContentParseError("Unable to decode file; expected UTF-8 text.")


def _find_header_row(rows: list[list[str]], text_headers: TextHeaders) -> int:
    """Locate the header row, skipping any leading comment/preamble rows.

    The header is the first row that contains recognisable sura + aya columns.
    """
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & SURA_HEADERS and normalized & AYA_HEADERS:
            return index
    raise AssetContentParseError("No recognisable header row (expected sura/aya + text columns).")


def _column_map(header: list[str], text_headers: TextHeaders) -> dict[str, int]:
    """Map canonical field names to their column index from the header row."""
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index
        elif key in AYA_HEADERS and "aya" not in mapping:
            mapping["aya"] = index

    mapping.update(_text_column_map(header, text_headers))
    missing = {"sura", "aya", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_surah_header_row(rows: list[list[str]], text_headers: TextHeaders) -> int:
    """Locate the header row for a surah-template file: a sura + text column."""
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & SURA_HEADERS and normalized & _any_text_header(text_headers):
            return index
    raise AssetContentParseError("No recognisable header row (expected a sura + text column).")


def _surah_column_map(header: list[str], text_headers: TextHeaders) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index

    mapping.update(_text_column_map(header, text_headers))
    missing = {"sura", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_page_header_row(rows: list[list[str]], text_headers: TextHeaders) -> int:
    """Locate the header row for a page-template file: a page + text column."""
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        if normalized & PAGE_HEADERS and normalized & _any_text_header(text_headers):
            return index
    raise AssetContentParseError("No recognisable header row (expected a page + text column).")


def _page_column_map(header: list[str], text_headers: TextHeaders) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in PAGE_HEADERS and "page" not in mapping:
            mapping["page"] = index

    mapping.update(_text_column_map(header, text_headers))
    missing = {"page", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def _find_word_header_row(rows: list[list[str]], text_headers: TextHeaders) -> int:
    """Locate the header row for a word-template file.

    Accepts either a ``word_id`` column or the full ``sura``/``aya``/``word``
    triple, plus text.
    """
    for index, row in enumerate(rows):
        normalized = {cell.strip().lower() for cell in row}
        has_word_id = bool(normalized & WORD_ID_HEADERS)
        has_triple = bool(
            (normalized & SURA_HEADERS) and (normalized & AYA_HEADERS) and (normalized & WORD_POSITION_HEADERS)
        )
        if (has_word_id or has_triple) and normalized & _any_text_header(text_headers):
            return index
    raise AssetContentParseError("No recognisable header row (expected word_id, or sura + aya + word, plus text).")


def _word_column_map(header: list[str], text_headers: TextHeaders) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, cell in enumerate(header):
        key = cell.strip().lower()
        if key in WORD_ID_HEADERS and "word_id" not in mapping:
            mapping["word_id"] = index
        elif key in SURA_HEADERS and "sura" not in mapping:
            mapping["sura"] = index
        elif key in AYA_HEADERS and "aya" not in mapping:
            mapping["aya"] = index
        elif key in WORD_POSITION_HEADERS and "word" not in mapping:
            mapping["word"] = index

    mapping.update(_text_column_map(header, text_headers))
    if "text" not in mapping:
        raise AssetContentParseError("Header is missing required columns: text.")
    if "word_id" not in mapping and not {"sura", "aya", "word"} <= mapping.keys():
        raise AssetContentParseError("Header is missing required columns: word_id, or sura + aya + word.")
    return mapping


def _parse_group_entries(
    rows: list[list[str]], log: _RowLog, text_headers: TextHeaders, range_headers: list[str]
) -> dict[tuple[int, ...], Cells]:
    """Parse a group file into ``{(from…, to…): cells}``, keyed by the raw end positions.

    Any repeated range is a problem (``DUPLICATE``), not only a conflicting one:
    a group file has no canonical row list a download would repeat blank.
    """
    header_index = next(
        (
            index
            for index, row in enumerate(rows)
            if set(range_headers) <= (normalized := {cell.strip().lower() for cell in row})
            and normalized & _any_text_header(text_headers)
        ),
        None,
    )
    if header_index is None:
        raise AssetContentParseError(f"No recognisable header row (expected {', '.join(range_headers)} + text).")
    header = rows[header_index]
    # An ayah-group header is a subset of a word-group one: a word file must not
    # pass for an ayah file with its word columns ignored.
    foreign = {name for names in RANGE_HEADERS_BY_TEMPLATE.values() for name in names} - set(range_headers)
    if foreign & {cell.strip().lower() for cell in header}:
        raise AssetContentParseError("The file's range columns belong to a different template.")
    columns = {name: index for index, cell in enumerate(header) if (name := cell.strip().lower()) in range_headers}
    columns.update(_text_column_map(header, text_headers))

    entries: dict[tuple[int, ...], Cells] = {}
    for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if len(row) <= max(columns.values()):
            log.unreadable(row, row_number)
            continue
        try:
            key = tuple(int(row[columns[name]].strip()) for name in range_headers)
        except (ValueError, AttributeError):
            log.unreadable(row, row_number)
            continue
        content = _row_cells(row, columns, text_headers)
        if key in entries and (any(entries[key]) or any(content)):
            log.problems[row_number] = DUPLICATE
        entries[key] = content
        log.row_of[key] = row_number
    return entries


def _read_rows(raw: bytes) -> list[list[str]]:
    text = _decode(raw)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise AssetContentParseError("File is empty.")
    return rows


def _parse_ayah_entries(rows: list[list[str]], log: _RowLog, text_headers: TextHeaders) -> dict[tuple[int, int], Cells]:
    """Parse an ayah-shaped file into {(sura, aya): text}. Unchanged from the
    original ayah-only parser: rows with a non-integer sura/aya are skipped
    (almost always stray preamble lines), and duplicate (sura, aya) pairs keep
    the last occurrence."""
    header_index = _find_header_row(rows, text_headers)
    columns = _column_map(rows[header_index], text_headers)

    entries: dict[tuple[int, int], Cells] = {}
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

        content = _row_cells(row, columns, text_headers)
        log.read(entries, (sura, aya), content, row_number)
    return entries


def _parse_surah_entries(rows: list[list[str]], log: _RowLog, text_headers: TextHeaders) -> dict[int, Cells]:
    header_index = _find_surah_header_row(rows, text_headers)
    columns = _surah_column_map(rows[header_index], text_headers)

    entries: dict[int, Cells] = {}
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

        content = _row_cells(row, columns, text_headers)
        log.read(entries, sura, content, row_number)
    return entries


def _parse_page_entries(rows: list[list[str]], log: _RowLog, text_headers: TextHeaders) -> dict[int, Cells]:
    header_index = _find_page_header_row(rows, text_headers)
    columns = _page_column_map(rows[header_index], text_headers)

    entries: dict[int, Cells] = {}
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

        content = _row_cells(row, columns, text_headers)
        log.read(entries, page, content, row_number)
    return entries


def _parse_word_entries(
    rows: list[list[str]], log: _RowLog, text_headers: TextHeaders
) -> tuple[dict[int, Cells] | dict[tuple[int, int, int], Cells], bool]:
    """Parse a word-shaped file. Returns (entries, used_word_id).

    When the header carries a ``word_id`` column it takes precedence and
    ``entries`` is keyed by that raw id; otherwise ``entries`` is keyed by the
    (sura, aya, word-position) triple.
    """
    header_index = _find_word_header_row(rows, text_headers)
    columns = _word_column_map(rows[header_index], text_headers)
    used_word_id = "word_id" in columns

    if used_word_id:
        by_word_id: dict[int, Cells] = {}
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
            content = _row_cells(row, columns, text_headers)
            log.read(by_word_id, word_id, content, row_number)
        return by_word_id, True

    by_triple: dict[tuple[int, int, int], Cells] = {}
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
        content = _row_cells(row, columns, text_headers)
        log.read(by_triple, (sura, aya, word), content, row_number)
    return by_triple, False


def parse_content_file(
    raw: bytes,
    spec: UnitSpec,
    asset: Asset,
    *,
    column_keys: list[str] | None = None,
    strict: bool = False,
    allowed_unit_ids: set[int] | None = None,
) -> list[ParsedEntry]:
    """Parse raw file bytes into rows keyed to the asset's template unit.

    Returns entries in file order. Raises ``AssetContentParseError`` when the
    file's columns do not match the template (a surah file uploaded to a
    page-based asset is a user error, not something to guess at) or when no
    row resolves to a real, in-range unit of the template.

    Lenient by default: unreadable rows, conflicting duplicates (the last one
    wins) and rows for units that do not exist are skipped. ``strict`` (uploads,
    whose content must be exactly what gets reviewed) instead raises
    ``AssetContentInvalidRowsError`` naming every such row that carries text.
    Group files are always strict. ``allowed_unit_ids`` (a translated language
    of a group asset: its source's ranges) flags any other valid unit as
    ``NOT_IN_SOURCE``.
    """
    strict = strict or spec.is_group
    column_keys = column_keys or [column.key for column in asset.text_columns()]
    text_headers = _text_headers(column_keys)
    rows = _read_rows(raw)
    log = _RowLog()

    resolved: dict[object, int] = {}  # raw key -> candidate unit_id
    texts: dict[object, Cells] = {}  # raw key -> cells

    if spec.template == AssetTemplateChoice.SURAH:
        entries = _parse_surah_entries(rows, log, text_headers)
        for sura, text in entries.items():
            resolved[sura] = sura
            texts[sura] = text

    elif spec.template == AssetTemplateChoice.AYAH:
        entries = _parse_ayah_entries(rows, log, text_headers)
        # Local import: the repository module imports this module at load
        # time, so importing it back at module scope here would be circular.
        # By call time both modules are fully loaded.
        from apps.content.repositories.asset_content import AssetContentRepository

        ayah_index = AssetContentRepository()._ayah_id_by_sura_aya()
        for (sura, aya), text in entries.items():
            ayah_id = ayah_index.get((sura, aya))
            if ayah_id is None:
                if any(text):
                    log.problems[log.row_of[(sura, aya)]] = UNKNOWN_UNIT
                continue
            resolved[(sura, aya)] = ayah_id
            texts[(sura, aya)] = text

    elif spec.template == AssetTemplateChoice.WORD:
        entries, used_word_id = _parse_word_entries(rows, log, text_headers)
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
                    if any(text):
                        log.problems[log.row_of[triple]] = UNKNOWN_UNIT
                    continue
                resolved[triple] = word_id
                texts[triple] = text

    elif spec.is_group:
        range_headers = RANGE_HEADERS_BY_TEMPLATE[spec.template]
        entries = _parse_group_entries(rows, log, text_headers, range_headers)
        from apps.content.repositories.asset_content import AssetContentRepository

        repo = AssetContentRepository()
        index = (
            repo._ayah_id_by_sura_aya()
            if spec.template == AssetTemplateChoice.AYAH_GROUP
            else repo._word_id_by_sura_aya_position()
        )
        half = len(range_headers) // 2
        for key, text in entries.items():
            start, end = index.get(key[:half]), index.get(key[half:])
            if start is None or end is None or start > end:
                if any(text):
                    log.problems[log.row_of[key]] = UNKNOWN_UNIT if start is None or end is None else RANGE_REVERSED
                continue
            resolved[key] = encode_group_key(start, end)
            texts[key] = text

    else:  # page
        entries = _parse_page_entries(rows, log, text_headers)
        for page, text in entries.items():
            resolved[page] = page
            texts[page] = text

    if spec.is_group and log.problems:
        # Before the "no rows" check: a group file whose only rows are bad is
        # reported row by row, not as an unreadable file.
        raise AssetContentInvalidRowsError(log.problems)
    if not resolved:
        raise AssetContentParseError(f"No {spec.template} rows found after the header.")

    valid_ids = spec.valid_unit_ids(asset, list(resolved.values()))
    for key, unit_id in resolved.items():
        if unit_id not in valid_ids and any(texts[key]):
            log.problems[log.row_of[key]] = UNKNOWN_UNIT
        elif allowed_unit_ids is not None and unit_id not in allowed_unit_ids and any(texts[key]):
            log.problems[log.row_of[key]] = NOT_IN_SOURCE
    if strict and log.problems:
        raise AssetContentInvalidRowsError(log.problems)
    # A blank cell means "no content for this unit" — downloads list every unit
    # with blanks, so re-uploading one must not create an empty entry per row.
    parsed = [
        ParsedEntry(unit_id=unit_id, cells={k: v for k, v in zip(column_keys, texts[key], strict=True) if v})
        for key, unit_id in resolved.items()
        if unit_id in valid_ids and any(texts[key])
    ]

    if not parsed:
        raise AssetContentParseError(f"No {spec.template} rows resolved to a valid unit of this asset's template.")

    logger.info(f"Parsed content file into {len(parsed)} {spec.template} entries")
    return parsed
