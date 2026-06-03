"""Extract entity IDs and names from a JSON response body for usage tracking events."""

from __future__ import annotations

import json

MAX_ENTITY_IDS = 1000  # was 100; matches Ninja MAX_PAGE_SIZE
_LIST_KEYS = ("items", "results", "data")
_NAME_KEYS = ("name_en", "name", "title_en", "title")


def extract_entities(body: bytes | None) -> tuple[list[int | str], list[str]]:
    """Return ``(ids, names)`` extracted from a JSON response body.

    Tries name keys in order: ``name_en``, ``name``, ``title_en``, ``title``.
    Falls back to empty string if none found. Both lists are the same length.

    Supported shapes:
      - flat list: ``[{"id": 1, "name_en": "Ibn Kathir"}, ...]``
      - paginated dict: ``{"results": [...]}``
      - single dict: ``{"id": 1, ...}``
    """
    if not body:
        return [], []

    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return [], []

    items = _items_from_payload(payload)
    ids: list[int | str] = []
    names: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        ids.append(item_id)
        names.append(_extract_name(item))
        if len(ids) >= MAX_ENTITY_IDS:
            break
    return ids, names


def extract_entity_ids(body: bytes | None) -> list[int | str]:
    """Backwards-compatible wrapper — returns IDs only."""
    ids, _ = extract_entities(body)
    return ids


def _extract_name(item: dict) -> str:
    for key in _NAME_KEYS:
        value = item.get(key)
        if value is not None and isinstance(value, str):
            return value
    return ""


def _items_from_payload(payload) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in _LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if "id" in payload:
            return [payload]
    return []
