---
sidebar_position: 4
title: Related Object Embeds
description: How the API embeds related resource data inline to eliminate extra round-trips.
---

# Related Object Embeds

Render lists without a second request.

## The Pattern

When a resource references another resource, the API embeds a compact object containing at minimum `id` and `name`. This gives you everything needed to render a UI card or list row from a single API call. The `id` is there when you need to fetch the full record later.

## Example: Recitation List

`GET /recitations/` returns items with four related-resource embeds:

```json
{
  "count": 38,
  "results": [
    {
      "id": 7,
      "name": "Hafs an Asim — Warsh",
      "description": "Complete recitation in the Hafs narration.",
      "publisher": { "id": 3, "name": "Itqan" },
      "reciter": { "id": 12, "name": "Mishary Rashid Alafasy" },
      "riwayah": { "id": 1, "name": "Hafs" },
      "qiraah": { "id": 2, "name": "Asim", "bio": "One of the seven canonical readers." },
      "surahs_count": 114
    }
  ]
}
```

| Field | Shape | Notes |
|---|---|---|
| `publisher` | `{id, name}` | Always present |
| `reciter` | `{id, name}` | Always present |
| `riwayah` | `{id, name}` or `null` | Null when not applicable |
| `qiraah` | `{id, name, bio}` or `null` | Includes one extra display field |

All `name` values are [localized](/docs/guides/localization) via `Accept-Language`.

## Stable Contract

This shape is stable. Future related resource embeds follow the same pattern: `id` first, `name` second, at most one optional extra display field. The API never embeds a full nested object — depth stays at one level.

## Anti-Pattern: Don't Avoid the Full Resource

If you need data beyond `id` and `name` — for example, the reciter's full biography or country — call the resource's own endpoint:

```bash
curl {{API_BASE}}/reciters/12/
```

Embedding full records would make list responses unboundedly large. The `id` in the embed is the stable pointer to use when you need more.

---

**See also:** [Design Principles](/docs/guides/api-design) · [Localization](/docs/guides/localization) · [Recitations & Ayah Timings](/docs/guides/recitations-ayah-timings)
