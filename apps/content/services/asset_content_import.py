"""Parse uploaded translation / tafsir content files into per-ayah rows.

Supported formats (both are the QuranEnc CSV export shapes present in the
project's sample data):

* Translation CSV: an optional multi-line comment/preamble row, then a header
  row ``id,sura,aya,translation,footnotes`` followed by one row per ayah.
* Tafsir CSV (Arabic QuranEnc): a header row that includes
  ``رقم السورة`` (sura number), ``رقم الآية`` (ayah number), ``المحتوى`` (content)
  and ``الهامش`` (margin / footnotes), plus import-only metadata columns.

The parser is header-driven, so it tolerates column reordering and the two
different schemas without a per-category branch at the call site.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
import io
import logging
import sys

logger = logging.getLogger(__name__)

# QuranEnc tafsir/translation rows can carry very large content cells.
csv.field_size_limit(sys.maxsize)

# Header aliases -> canonical field. Lower-cased / stripped before lookup.
_SURA_HEADERS = {"sura", "surah", "رقم السورة"}
_AYA_HEADERS = {"aya", "ayah", "رقم الآية"}
_TEXT_HEADERS = {"translation", "text", "content", "المحتوى"}
_FOOTNOTE_HEADERS = {"footnotes", "footnote", "الهامش"}


@dataclass(frozen=True)
class ParsedEntry:
    """One parsed per-ayah row, keyed by (sura, aya) within its sura."""

    sura: int
    aya: int
    text: str
    footnotes: str


class AssetContentParseError(Exception):
    """Raised when an uploaded content file cannot be parsed into ayah rows."""


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
        elif key in _FOOTNOTE_HEADERS and "footnotes" not in mapping:
            mapping["footnotes"] = index

    missing = {"sura", "aya", "text"} - mapping.keys()
    if missing:
        raise AssetContentParseError(f"Header is missing required columns: {', '.join(sorted(missing))}.")
    return mapping


def parse_content_file(raw: bytes) -> list[ParsedEntry]:
    """Parse raw file bytes into per-ayah entries.

    Returns entries in file order. Rows with a non-integer sura/aya are skipped
    (they are almost always stray preamble lines), and duplicate (sura, aya)
    pairs keep the last occurrence.
    """
    text = _decode(raw)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise AssetContentParseError("File is empty.")

    header_index = _find_header_row(rows)
    columns = _column_map(rows[header_index])
    footnote_col = columns.get("footnotes")

    entries: dict[tuple[int, int], ParsedEntry] = {}
    for row in rows[header_index + 1 :]:
        max_needed = max(columns.values())
        if len(row) <= max_needed:
            continue
        try:
            sura = int(row[columns["sura"]].strip())
            aya = int(row[columns["aya"]].strip())
        except (ValueError, AttributeError):
            continue

        content = (row[columns["text"]] or "").strip()
        footnotes = ""
        if footnote_col is not None and len(row) > footnote_col:
            footnotes = (row[footnote_col] or "").strip()

        entries[(sura, aya)] = ParsedEntry(sura=sura, aya=aya, text=content, footnotes=footnotes)

    if not entries:
        raise AssetContentParseError("No ayah rows found after the header.")

    logger.info(f"Parsed content file into {len(entries)} ayah entries")
    return list(entries.values())
