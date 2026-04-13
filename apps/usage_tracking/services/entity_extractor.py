"""Extract entity IDs from a JSON response body for usage tracking events."""

from __future__ import annotations

import json

MAX_ENTITY_IDS = 100
_LIST_KEYS = ("items", "results", "data")


def extract_entity_ids(body: bytes | None) -> list[int | str]:
    """Return up to ``MAX_ENTITY_IDS`` entity IDs found in a JSON response body.

    Supported shapes:
      - flat list: ``[{"id": 1}, {"id": 2}]``
      - paginated dict: ``{"items"|"results"|"data": [{"id": 1}, ...]}``
      - single dict: ``{"id": 1, ...}``

    Non-dict entries in lists are silently skipped. Anything that fails to
    parse as JSON returns an empty list.
    """
    if not body:
        return []

    try:
        payload = json.loads(body)
    except (ValueError, TypeError):
        return []

    items = _items_from_payload(payload)
    ids: list[int | str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        if item_id is None:
            continue
        ids.append(item_id)
        if len(ids) >= MAX_ENTITY_IDS:
            break
    return ids


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
