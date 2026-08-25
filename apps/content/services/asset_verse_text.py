"""Verse-level text extraction from Tafsir/Translation AssetVersion files.

Tafsir and Translation assets keep their content as uploaded files on
``AssetVersion.file_url`` (``Asset`` rows hold metadata only), so this module is
the retrieval path that turns the latest version file into the text for one
``(surah, ayah)`` location.

Supported payloads are UTF-8 JSON objects in either shape:

    {"1:1": "بِسْمِ اللَّهِ...", ...}                    # flat "surah:ayah" keys
    {"1": {"1": "بِسْمِ اللَّهِ...", "2": "..."}, ...}   # nested surah -> ayah

Anything else -- PDF/DOCX uploads, malformed JSON, non-dict payloads, or a
missing verse -- yields ``None`` so callers report honest unavailability
instead of fabricating text.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from django.core.cache import cache

if TYPE_CHECKING:
    from apps.content.models import Asset, AssetVersion

logger = logging.getLogger(__name__)

SAMPLE_VERSE_CACHE_TTL = 60 * 5  # aligned with the other public-sample cache TTLs
_TEXT_SENTINEL = ""  # negative-caching marker so absent verses skip storage reads too


def extract_verse_text(asset: Asset, surah: int, ayah: int) -> str | None:
    """
    Text for one ayah from the asset's latest version file, cached per version.

    Returns None when the asset has no usable JSON payload or the requested
    location is absent. Results (including misses) are cached so repeated
    sample requests do not re-read the stored file. The latest version is
    resolved exactly once per call.
    """
    latest = asset.get_latest_version()
    # The key carries BOTH the selected row's identity and its last-modified
    # stamp at FULL microsecond precision, so stale text can never outlive the
    # version row that produced it:
    # - a NEW AssetVersion row becomes latest -> different pk -> fresh key;
    # - an IN-PLACE edit (portal PUT/PATCH re-saving the same row) bumps
    #   updated_at (BaseModel auto_now) -> rotated key without any signals.
    # Sub-second precision matters: consecutive saves routinely land within
    # the same wall-clock second.
    if latest is None:
        version_token = "none"
    else:
        version_token = f"{latest.pk}:{latest.updated_at.isoformat()}"
    cache_key = f"sample-verse-text:{asset.pk}:{version_token}:{surah}:{ayah}"
    cached = cache.get(cache_key)
    if cached is not None:
        return None if cached == _TEXT_SENTINEL else cached

    text = _lookup_verse(_read_version_json(latest), surah, ayah)
    cache.set(cache_key, text if text is not None else _TEXT_SENTINEL, SAMPLE_VERSE_CACHE_TTL)
    return text


def _read_version_json(version: AssetVersion | None) -> dict[str, Any] | None:
    """Parse one AssetVersion file into a dict, or None when unusable."""
    if version is None or not version.file_url:
        return None
    # Only text-JSON candidates are read; PDF/DOCX/ZIP uploads can never yield verses.
    if not version.file_url.name.lower().endswith((".json", ".txt")):
        return None
    try:
        with version.file_url.open("rb") as fh:
            payload = json.loads(fh.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        # json.JSONDecodeError subclasses ValueError. Narrow on purpose: real
        # storage/encoding/payload faults become honest unavailability, while
        # unexpected code bugs still propagate loudly.
        logger.warning("Failed to parse verse file %s: %s", version.pk, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _lookup_verse(payload: dict[str, Any] | None, surah: int, ayah: int) -> str | None:
    """
    Resolve one ``(surah, ayah)`` location inside a parsed payload.

    Tries the flat ``"surah:ayah"`` key first, then the nested
    ``{"<surah>": {"<ayah>": ...}}`` shape. Blank or non-string values count as
    absent so callers never surface whitespace-only "verses".
    """
    if not payload:
        return None

    flat = payload.get(f"{surah}:{ayah}")
    if isinstance(flat, str) and flat.strip():
        return flat

    nested = payload.get(str(surah))
    if isinstance(nested, dict):
        value = nested.get(str(ayah))
        if isinstance(value, str) and value.strip():
            return value

    return None
