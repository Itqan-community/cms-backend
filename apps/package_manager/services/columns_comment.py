"""The ``# itqan:columns`` comment block above a manifest entry.

The itqan CLI writes it when adding a multi-column translation / tafsir, and
Dependabot refreshes it when a bump changes the columns. Both must render it
byte for byte the same; the format is specified in docs/ASSET_MANIFEST.md
("Column comment block").
"""

from __future__ import annotations

from apps.content.services.asset_columns import VersionStructure

MARKER = "# itqan:columns"


def _one_line(value: str) -> str:
    """``value`` with every run of whitespace (newlines included) as one space: a
    publisher-typed label must never become a line of YAML of its own."""
    return " ".join(value.split())


def render_columns_comment(structure: VersionStructure, indent: str) -> list[str]:
    """The block's lines (no trailing newlines) at ``indent``; none for a single column."""
    if len(structure.columns) <= 1:
        return []
    header = ", ".join(_one_line(name) for name in structure.header)
    lines = [f"{indent}{MARKER} CSV, one row per {_one_line(structure.template)}: {header}"]
    for column in structure.columns:
        labels = " / ".join(_one_line(label) for label in (column.label_en, column.label_ar) if _one_line(label))
        if labels:
            lines.append(f"{indent}{MARKER}   {_one_line(column.key)}: {labels}")
    return lines
