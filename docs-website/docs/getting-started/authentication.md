---
sidebar_position: 2
---

# Authentication

Itqan APIs use an **API key** to identify your application. Public read endpoints currently work without one, but we recommend creating a key now — it unlocks account-aware features, higher rate limits, and keeps your integration ready as authentication rolls out more widely.

## Get an API key

1. Sign in to the Asset Library at **[cms.itqan.dev](https://cms.itqan.dev)**.
2. Open your account settings and go to **API Keys**.
3. Create a key, give it a descriptive name (e.g. `my-recitation-app`), and copy it.

> **Store it securely.** Treat the key like a password — keep it in an environment variable or secret manager, never commit it to source control or expose it in client-side code.

## Send the key

Pass your key on every request in the `X-API-Key` header:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="curl" label="curl">

```bash
curl {{API_BASE}}/reciters/ \
  -H "X-API-Key: YOUR_API_KEY"
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request
import json

req = urllib.request.Request(
    "{{API_BASE}}/reciters/",
    headers={"X-API-Key": "YOUR_API_KEY"},
)
with urllib.request.urlopen(req) as resp:
    data = json.load(resp)

print(f"Total reciters: {data['count']}")
```

</TabItem>
<TabItem value="js" label="JavaScript">

```js
const resp = await fetch("{{API_BASE}}/reciters/", {
  headers: { "X-API-Key": "YOUR_API_KEY" },
});
const { count, results } = await resp.json();

console.log(`Total reciters: ${count}`);
```

</TabItem>
</Tabs>

## Errors

A missing or invalid key returns an error in the [standard error format](/docs/guides/errors):

| Status | Meaning | Fix |
|--------|---------|-----|
| `401 Unauthorized` | Key is missing or malformed | Add a valid `X-API-Key` header |
| `403 Forbidden` | Key is valid but not allowed for this resource | Check the key's permissions in the Asset Library |

Existing integrations against public read endpoints continue to work without disruption while the key requirement is phased in.

---

**See also:** [Quickstart](/docs/getting-started/quickstart) · [Error Handling](/docs/guides/errors)
