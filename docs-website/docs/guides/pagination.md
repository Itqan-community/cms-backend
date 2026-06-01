---
sidebar_position: 3
title: Pagination
description: How to page through large result sets using the page and page_size parameters.
---

# Pagination

## Parameters

| Parameter | Type | Default | Max |
|---|---|---|---|
| `page` | integer (1-indexed) | `1` | — |
| `page_size` | integer | `20` | `1000` |

Both parameters are optional. Omitting them returns the first 20 results. Values above 1 000 for `page_size` are silently clamped to 1 000.

## Paging Through Results

Use `count` from the [response envelope](/docs/guides/response-structure) to determine how many pages exist, then increment `page` until you have all records.

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

---

**See also:** [Response Structure](/docs/guides/response-structure) · [Searching, Filtering, Ordering](/docs/guides/search-filter-order) · [Error Handling](/docs/guides/errors)
