---
sidebar_position: 2
title: Response Structure
description: How list and single-resource responses are structured in the Itqan CMS API.
---

# Response Structure

## Envelope Shape

All list endpoints return a consistent envelope:

```json
{
  "count": 150,
  "results": [
    { "id": 1, "name": "..." },
    { "id": 2, "name": "..." }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `count` | integer | Total number of matching records across all pages |
| `results` | array | The items on the current page |

`count` is the total across all pages — not just the page you received. Use it to calculate how many pages exist.

## Single-Resource Responses

Single-resource endpoints (for example, `GET /recitations/{id}/`) return the object directly with no envelope:

```json
{
  "id": 7,
  "name": "Hafs an Asim",
  "description": "Complete recitation in the Hafs narration.",
  "publisher": { "id": 3, "name": "Itqan" },
  "reciter": { "id": 12, "name": "Mishary Rashid Alafasy" },
  "riwayah": { "id": 1, "name": "Hafs" }
}
```

---

**See also:** [Pagination](/docs/guides/pagination) · [Design Principles](/docs/guides/api-design) · [Error Handling](/docs/guides/errors)
