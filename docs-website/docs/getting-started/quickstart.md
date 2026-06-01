---
sidebar_position: 1
---

# Quickstart

The **Itqan CMS API** gives you authentic Quranic recitation data — reciters, recitations, riwayahs, qiraat, and ayah-level audio timings — from verified publishers, over a clean REST/JSON interface. No SDK, no setup: every endpoint is a plain `GET` you can run from a terminal right now.

## Your first request

> **Time:** ~30 seconds. Copy, paste, run — no API key required to read public content.

Base URL: `{{API_BASE}}`

List the reciters available in the catalog:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
curl {{API_BASE}}/reciters/
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request
import json

with urllib.request.urlopen("{{API_BASE}}/reciters/") as resp:
    data = json.load(resp)

print(f"Total reciters: {data['count']}")
for reciter in data["results"]:
    print(f"  {reciter['name']} — {reciter['recitations_count']} recitations")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const resp = await fetch("{{API_BASE}}/reciters/");
const { count, results } = await resp.json();

console.log(`Total reciters: ${count}`);
results.forEach((r) => console.log(`  ${r.name} — ${r.recitations_count} recitations`));
```

</TabItem>
</Tabs>

**Response:**

```json
{
  "count": 42,
  "results": [
    {
      "id": 1,
      "name": "Mishary Rashid Alafasy",
      "bio": "...",
      "recitations_count": 3
    }
  ]
}
```

That's a live integration. Want Arabic instead? Add `-H "Accept-Language: ar"` and every `name`, `description`, and `bio` comes back localized.

→ Full endpoint reference: [List Reciters](/docs/reference/api/apps-content-api-public-reciters-list-reciters)

## Designed with care for developers

- **Render from one request.** Related resources are embedded as compact `{id, name}` objects, so a single response carries everything you need for a complete list item. → [Related Resources](/docs/guides/related-resources)
- **One field, any language.** Ask for Arabic or English with an `Accept-Language` header — the JSON keys never change, only the values. → [Localization](/docs/guides/localization)
- **Stable, predictable shapes.** Plural-noun paths, a consistent `{count, results}` envelope, and a unified error format make clients easy to write. → [Design Principles](/docs/guides/api-design)
- **Safe to build against.** Resource IDs are stable integers and the API evolves additively — new fields never break existing integrations.

## What's next

- [API Reference](/docs/reference/api/) — every endpoint, with interactive examples
- [Design Principles](/docs/guides/api-design) — the conventions behind the API
- [Error Handling](/docs/guides/errors) — build resilient clients
