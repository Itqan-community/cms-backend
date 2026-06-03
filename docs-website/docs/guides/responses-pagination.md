---
sidebar_position: 2
title: Response Envelope & Pagination
description: How paginated list responses are structured, and how to page through large result sets.
---

# Response Envelope & Pagination

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

Single-resource endpoints (for example, `GET /recitations/{id}/`) return the object directly with no envelope.

## Pagination Parameters

| Parameter | Type | Default | Max |
|---|---|---|---|
| `page` | integer (1-indexed) | `1` | — |
| `page_size` | integer | `20` | `1000` |

Both parameters are optional. Omitting them returns the first 20 results.

## Paging Through Results

Use `count` to determine how many pages exist, then increment `page` until you have all records.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
# Page 1
curl "{{API_BASE}}/reciters/?page=1&page_size=10"

# Page 2
curl "{{API_BASE}}/reciters/?page=2&page_size=10"
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.parse, json

BASE = "{{API_BASE}}"
PAGE_SIZE = 50

def fetch_all_reciters():
    results = []
    page = 1
    while True:
        params = urllib.parse.urlencode({"page": page, "page_size": PAGE_SIZE})
        url = f"{BASE}/reciters/?{params}"
        with urllib.request.urlopen(url) as resp:
            body = json.load(resp)
        results.extend(body["results"])
        if len(results) >= body["count"]:
            break
        page += 1
    return results
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const BASE = "{{API_BASE}}";
const PAGE_SIZE = 50;

async function fetchAllReciters() {
  const results = [];
  let page = 1;
  while (true) {
    const resp = await fetch(`${BASE}/reciters/?page=${page}&page_size=${PAGE_SIZE}`);
    const { count, results: items } = await resp.json();
    results.push(...items);
    if (results.length >= count) break;
    page++;
  }
  return results;
}
```

</TabItem>
</Tabs>

## Large Page Sizes

Set `page_size=1000` to fetch up to 1 000 records in a single request. This is the hard cap; values above 1 000 are silently clamped to 1 000.

---

**See also:** [Design Principles](/docs/guides/api-design) · [Searching, Filtering, Ordering](/docs/guides/search-filter-order) · [Error Handling](/docs/guides/errors)
