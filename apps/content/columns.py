"""Pure helpers for the text columns of translation / tafsir assets.

A text asset stores one *cell* per (unit, column): ``CellKey`` names it and a
``Snapshot`` holds a whole version's cells. Shared by the content repository,
the importer, the package catalog and the manifest comment block, so the CSV
header and the key rules live in one place.
"""

from __future__ import annotations

import re

from django.utils.translation import gettext_lazy as _

from apps.content.models import AssetTemplateChoice
from apps.core.ninja_utils.errors import ItqanError

# (unit_id, column_key)
CellKey = tuple[int, str]
Snapshot = dict[CellKey, str]

# Header aliases the importer accepts for each unit field (matched lower-cased and stripped).
SURA_HEADERS = frozenset({"sura", "surah", "رقم السورة"})
AYA_HEADERS = frozenset({"aya", "ayah", "رقم الآية"})
PAGE_HEADERS = frozenset({"page", "page_no", "رقم الصفحة"})
WORD_ID_HEADERS = frozenset({"word_id", "word_index"})
WORD_POSITION_HEADERS = frozenset({"word", "position", "رقم الكلمة"})

# A group template's row names its range by both ends (exact names, no aliases).
RANGE_HEADERS_BY_TEMPLATE: dict[str, list[str]] = {
    AssetTemplateChoice.AYAH_GROUP: ["from_surah", "from_ayah", "to_surah", "to_ayah"],
    AssetTemplateChoice.WORD_GROUP: ["from_surah", "from_ayah", "from_word", "to_surah", "to_ayah", "to_word"],
}
# The covered Quran text a verbose group export carries; the importer ignores it.
REFERENCE_TEXT_HEADER = "reference_text"

# Names the unit part of a CSV uses (export headers and import aliases): a column
# key may not shadow them.
UNIT_HEADERS: frozenset[str] = frozenset(
    {"surah_name", "ayah_text", REFERENCE_TEXT_HEADER}.union(
        SURA_HEADERS,
        AYA_HEADERS,
        PAGE_HEADERS,
        WORD_ID_HEADERS,
        WORD_POSITION_HEADERS,
        *RANGE_HEADERS_BY_TEMPLATE.values(),
    )
)

# Not unit headers, but taken by the portal's column routes (`columns/order/`).
_RESERVED_KEYS = frozenset({"order"})

# ASCII only, so developers can use a key as a CSV header, a JSON field or an identifier.
_KEY_RE = re.compile(r"[a-z][a-z0-9_]{0,63}")

_UNIT_HEADER_BY_TEMPLATE: dict[str, list[str]] = {
    AssetTemplateChoice.SURAH: ["sura"],
    AssetTemplateChoice.AYAH: ["surah", "ayah"],
    AssetTemplateChoice.WORD: ["word_id", "sura", "aya", "word"],
    AssetTemplateChoice.PAGE: ["page"],
    **RANGE_HEADERS_BY_TEMPLATE,
}


def validate_column_key(key: str) -> None:
    """Raise ``column_key_invalid`` unless ``key`` is a usable column key."""
    if not _KEY_RE.fullmatch(key or "") or key in UNIT_HEADERS or key in _RESERVED_KEYS:
        raise ItqanError(
            error_name="column_key_invalid",
            message=_(
                "A column key must start with a lowercase English letter (a-z), use only a-z, 0-9 and "
                "underscores (at most 64), and must not be a unit name such as sura or ayah."
            ),
            status_code=400,
        )


def requires_major_bump(previous_keys: list[str], new_keys: list[str]) -> bool:
    """Whether going from ``previous_keys`` to ``new_keys`` changes the file layout
    for code reading columns by position: the previous keys no longer appear in
    the same relative order. Adding columns anywhere is not such a change."""
    kept = [key for key in new_keys if key in set(previous_keys)]
    return kept != [key for key in previous_keys if key in set(new_keys)]


def csv_header(template: str, column_keys: list[str], *, verbose: bool = False) -> list[str]:
    """The CSV header for ``template`` with one text column per key.

    ``verbose`` only changes the ayah template, which then also carries the
    surah name and the ayah text for reviewers, and the group templates, which
    then carry the covered Quran text (``reference_text``).
    """
    if verbose and template == AssetTemplateChoice.AYAH:
        units = ["surah", "ayah", "surah_name", "ayah_text"]
    elif verbose and template in RANGE_HEADERS_BY_TEMPLATE:
        units = [*RANGE_HEADERS_BY_TEMPLATE[template], REFERENCE_TEXT_HEADER]
    else:
        units = _UNIT_HEADER_BY_TEMPLATE[template]
    return [*units, *column_keys]
