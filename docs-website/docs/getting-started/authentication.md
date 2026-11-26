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

## Identify end users

For per-end-user usage metrics, include an opaque, developer-chosen identifier in
the `X-External-User-Id` header. Do not send names, email addresses, phone
numbers, or other personally identifiable information. The value is treated as
opaque metadata and is scoped to the application identified by your API key.

```bash
curl {{API_BASE}}/reciters/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-External-User-Id: user-123"
```

The identifier may contain letters, numbers, `.`, `_`, `:`, and `-`, must start
with a letter or number, and may be up to 64 characters long. Values that are
empty, contain an email address, resemble a phone number, or use other invalid
characters are rejected with `400 invalid_external_user_id`.

## Errors

Key errors use the [standard error format](/docs/guides/errors):

| Status | `error_name` | Meaning | Fix |
|--------|--------------|---------|-----|
| `401 Unauthorized` | `invalid_api_key` | The `X-API-Key` header is set, but the key does not exist, was revoked or has expired | Create a new key in the Asset Library, or drop the header to call as an anonymous client |
| `401 Unauthorized` | `authentication_required` | The resource needs a key and none was sent | Add a valid `X-API-Key` header |
| `403 Forbidden` | `access_denied` | The key is valid but its account has no access to this resource | Request access to the asset in the Asset Library |

Public read endpoints still work without a key. A key that is sent is always checked: an invalid one is rejected with `401 invalid_api_key` and is never treated as an anonymous call.

---

**See also:** [Quickstart](/docs/getting-started/quickstart) · [Error Handling](/docs/guides/errors)
