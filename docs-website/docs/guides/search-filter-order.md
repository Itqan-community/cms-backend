---
sidebar_position: 6
title: Searching, Filtering, Ordering
description: How to search, filter, and sort results across Itqan CMS API endpoints.
---

# Searching, Filtering, Ordering

Three query primitives control what you get and in what order. All three can be combined in a single request.

## Search (`search=`)

Free-text search across name, description, and related resource names (both Arabic and English). The match is case-insensitive and searches for records containing the term.

```bash
curl "{{API_BASE}}/recitations/?search=mishary"
```

On `/recitations/`, the `search` parameter matches against:
- `name`
- `description`
- `publisher.name`
- `reciter.name` (Arabic and English)
- `riwayah.name` (Arabic and English)
- `qiraah.name` (Arabic and English)

Multiple words are ANDed — `search=hafs+asim` returns records matching both "hafs" and "asim".

## Filtering

Endpoints expose per-resource filter parameters. All accept comma-separated or repeated values (multi-value OR).

### Recitations (`/recitations/`)

| Parameter | Type | Description |
|---|---|---|
| `publisher_id` | integer (repeatable) | Filter by publisher ID |
| `reciter_id` | integer (repeatable) | Filter by reciter ID |
| `riwayah_id` | integer (repeatable) | Filter by riwayah ID |
| `qiraah_id` | integer (repeatable) | Filter by qiraah ID |

Pass a parameter multiple times to match any of the values (OR logic):

```bash
# Recitations by reciter 12 OR reciter 15
curl "{{API_BASE}}/recitations/?reciter_id=12&reciter_id=15"
```

## Ordering (`ordering=`)

Sort results by one or more fields. Prefix a field name with `-` for descending order. Separate multiple fields with a comma.

### Recitations (`/recitations/`)

Allowed fields: `name`, `created_at`, `updated_at`

```bash
# Alphabetical by name (ascending)
curl "{{API_BASE}}/recitations/?ordering=name"

# Most recently updated first
curl "{{API_BASE}}/recitations/?ordering=-updated_at"
```

### Reciters (`/reciters/`) and Riwayahs (`/riwayahs/`)

Allowed field: `name`

```bash
curl "{{API_BASE}}/reciters/?ordering=-name"
```

## Combining All Three

```bash
curl "{{API_BASE}}/recitations/\
?search=hafs\
&publisher_id=3\
&reciter_id=12\
&ordering=-created_at\
&page=1\
&page_size=20"
```

This returns recitations matching "hafs", published by publisher 3, by reciter 12, sorted newest first, page 1.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.parse, json

params = urllib.parse.urlencode({
    "search": "hafs",
    "publisher_id": 3,
    "reciter_id": 12,
    "ordering": "-created_at",
    "page": 1,
    "page_size": 20,
})
url = f"{{API_BASE}}/recitations/?{params}"

with urllib.request.urlopen(url) as resp:
    data = json.load(resp)

print(f"{data['count']} matching recitations")
for r in data["results"]:
    print(f"  [{r['id']}] {r['name']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const params = new URLSearchParams({
  search: "hafs",
  publisher_id: 3,
  reciter_id: 12,
  ordering: "-created_at",
  page: 1,
  page_size: 20,
});
const resp = await fetch(`{{API_BASE}}/recitations/?${params}`);
const { count, results } = await resp.json();

console.log(`${count} matching recitations`);
results.forEach(r => console.log(`  [${r.id}] ${r.name}`));
```

</TabItem>
</Tabs>

---

**See also:** [Pagination](/docs/guides/pagination) · [Related Object Embeds](/docs/guides/related-resources) · [API Reference](/docs/reference/api/)
