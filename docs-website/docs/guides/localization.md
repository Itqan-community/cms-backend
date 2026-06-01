---
sidebar_position: 3
title: Localization
description: How to request Arabic or English content using the Accept-Language header.
---

# Localization

One request, one key — language follows the header.

## How It Works

Send an `Accept-Language` header with each request. The API returns the same JSON structure with localized text fields reflecting your language choice. There are no `name_ar` / `name_en` split keys in the response — the `name` key always appears, and its value is in the requested language.

| Header value | Language returned |
|---|---|
| `Accept-Language: en` (default) | English |
| `Accept-Language: ar` | Arabic |

If the header is omitted or set to an unsupported locale, the API falls back to English.

## Localized Fields by Resource

| Resource | Localized fields |
|---|---|
| Recitation | `name`, `description` |
| Reciter | `name`, `bio` |
| Riwayah | `name`, `bio` |
| Qiraah | `name` |
| Publisher | `name` |

Related resource embeds (`publisher.name`, `reciter.name`, etc.) inside a recitation response are also localized — you get Arabic names throughout the payload with a single header.

## Example

The same `/reciters/` endpoint with two different `Accept-Language` values:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
# English (default)
curl -H "Accept-Language: en" {{API_BASE}}/reciters/

# Arabic
curl -H "Accept-Language: ar" {{API_BASE}}/reciters/
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, json

url = "{{API_BASE}}/reciters/"

for lang in ("en", "ar"):
    req = urllib.request.Request(url, headers={"Accept-Language": lang})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    print(f"[{lang}] first reciter name: {data['results'][0]['name']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const url = "{{API_BASE}}/reciters/";

for (const lang of ["en", "ar"]) {
  const resp = await fetch(url, { headers: { "Accept-Language": lang } });
  const { results } = await resp.json();
  console.log(`[${lang}] first reciter name: ${results[0].name}`);
}
```

</TabItem>
</Tabs>

**English response:**

```json
{
  "count": 42,
  "results": [
    { "id": 1, "name": "Mishary Rashid Alafasy", "bio": "...", "recitations_count": 5 }
  ]
}
```

**Arabic response:**

```json
{
  "count": 42,
  "results": [
    { "id": 1, "name": "مشاري راشد العفاسي", "bio": "...", "recitations_count": 5 }
  ]
}
```

Same `id`, same structure — only the text values differ.

---

**See also:** [Design Principles](/docs/guides/api-design) · [Related Object Embeds](/docs/guides/related-resources) · [Error Handling](/docs/guides/errors)
