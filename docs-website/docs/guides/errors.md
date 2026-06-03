---
sidebar_position: 7
title: Error Handling
description: The unified error envelope, full error catalog, and client-side handling patterns.
---

# Error Handling

Every non-2xx response from the Itqan CMS API uses the same envelope. Build your error handling once and it covers every endpoint.

## Error Envelope

```json
{
  "error_name": "not_found",
  "message": "No asset matches the given query.",
  "extra": null
}
```

| Field | Type | Description |
|---|---|---|
| `error_name` | string | **Stable machine identifier.** Switch on this in code, not on `message` or HTTP status. Never contains spaces. |
| `message` | string | Human-readable description. Localized via `Accept-Language` — safe to display directly to users. |
| `extra` | object or null | Optional structured detail. Shape varies by error type (see catalog below). |

## Error Catalog

| HTTP | `error_name` | Triggered by | `extra` shape |
|---|---|---|---|
| 400 | `validation_error` | Invalid query parameters or request body | Array of field-level error objects |
| 400 | `invalid_json` | Malformed JSON request body | `null` |
| 401 | `authentication_error` | Missing or invalid credentials | `null` |
| 401 | `token_not_valid` | Expired or revoked JWT token | `null` |
| 403 | `permission_denied` | Authenticated but not authorized | `null` |
| 404 | `not_found` | Resource does not exist | `null` |
| 4xx/5xx | `http_error` | Generic HTTP error path | `null` |
| 500 | `internal_error` | Unhandled server exception | `null` |
| varies | *(custom)* | Business logic error via `ItqanError` | Per-endpoint; documented in the endpoint's Reference page |

### `validation_error` Extra Shape

When `error_name` is `validation_error`, `extra` contains an array of field-level error objects:

```json
{
  "error_name": "validation_error",
  "message": "Invalid Input",
  "extra": [
    { "loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal" }
  ]
}
```

## Client Handling

Branch on `error_name`. Do not branch on `message` (it changes with locale) or on HTTP status alone (multiple error names share the same status code).

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs groupId="language">
<TabItem value="js" label="JavaScript">

```js
async function apiFetch(url, options = {}) {
  const resp = await fetch(url, options);
  if (resp.ok) return resp.json();

  const error = await resp.json();

  switch (error.error_name) {
    case "not_found":
      // Resource doesn't exist — handle gracefully
      return null;
    case "validation_error":
      // Show field errors to the user
      throw new ValidationError(error.message, error.extra);
    case "authentication_error":
    case "token_not_valid":
      // Redirect to login or refresh token
      redirectToLogin();
      return;
    case "internal_error":
      // Retry with exponential backoff
      throw new RetryableError(error.message);
    default:
      // Unknown error — treat as internal
      throw new Error(error.message);
  }
}
```

</TabItem>
<TabItem value="python" label="Python">

```python
import urllib.request, urllib.error, json

def api_fetch(url):
    try:
        with urllib.request.urlopen(url) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        error = json.load(e)
        name = error.get("error_name")

        if name == "not_found":
            return None
        elif name == "validation_error":
            raise ValueError(f"Validation failed: {error['extra']}")
        elif name in ("authentication_error", "token_not_valid"):
            raise PermissionError("Authentication required")
        elif name == "internal_error":
            raise RuntimeError("Server error — retry with backoff")
        else:
            raise RuntimeError(error["message"])
```

</TabItem>
</Tabs>

### Key Rules

- **Branch on `error_name`**, not `message` or HTTP status.
- **Display `message` to users** — it is already localized via `Accept-Language`.
- **Treat unknown `error_name` as `internal_error`** — the API may add new error names; your client must not crash on them.
- **Retry with backoff on 5xx only** — 4xx errors are client errors and won't resolve on retry.

## Custom Endpoint Errors

Some endpoints raise `ItqanError` for business-logic conditions (for example, a conflict or a domain validation failure). These produce a custom `error_name` specific to that endpoint. Each endpoint's API Reference page documents the custom error names it can return.

---

**See also:** [Design Principles](/docs/guides/api-design) · [API Reference](/docs/reference/api/) · [Authentication](/docs/getting-started/authentication)
