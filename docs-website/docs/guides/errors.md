---
sidebar_position: 7
title: Error Handling
description: The unified error envelope, full error catalog, and client-side handling patterns.
---

# Error Handling

Every non-2xx response from the Fanar API uses the same envelope. Build your error handling once and it covers every endpoint.

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
| `extra` | object, array or null | Optional structured detail. Shape varies by error type (see catalog below). It is `null` whenever an error has no details, never an empty object. |

## Error Catalog

| HTTP | `error_name` | Triggered by | `extra` shape |
|---|---|---|---|
| 400 | `validation_error` | Invalid query parameters or request body, or values that don't make sense together (e.g. an ayah range whose `from` is after `to`). Validation errors always use `400` | Array of field-level error objects, or `null` |
| 400 | `invalid_external_user_id` | The `X-External-User-Id` header is empty, too long, looks like personal data or has invalid characters | `null` |
| 400 | `invalid_json` | Malformed JSON request body | `null` |
| 401 | `authentication_error` | Missing or invalid credentials | `null` |
| 401 | `invalid_api_key` | The `X-API-Key` header holds a key that does not exist, was revoked or has expired. Calls without the header are not affected | `null` |
| 401 | `token_not_valid` | Expired or revoked JWT token | `null` |
| 403 | `permission_denied` | Authenticated but not authorized | `null` |
| 404 | `not_found` | Resource does not exist | `null` |
| 429 | `throttled` | Rate limit exceeded (see [Rate Limits](#rate-limits)) | `null` |
| 4xx/5xx | `http_error` | Generic HTTP error path | `null` |
| 500 | `internal_error` | Unhandled server exception | `null` |
| varies | *(custom)* | Business logic error via `ItqanError` | Per-endpoint; documented in the endpoint's Reference page |

### `validation_error` Extra Shape

`extra` depends on what failed, so check its type before reading it:

- **A parameter or body field is invalid**: an array of field-level error objects, one per invalid field:

```json
{
  "error_name": "validation_error",
  "message": "Invalid Input",
  "extra": [
    { "loc": ["query", "page"], "msg": "Input should be greater than or equal to 1", "type": "greater_than_equal" }
  ]
}
```

- **The values don't make sense together**: `null`. Each value is valid on its own, and `message` says what is wrong:

```json
{
  "error_name": "validation_error",
  "message": "Invalid ayah range: from (5) must not exceed to (3).",
  "extra": null
}
```

Show `message` in both cases. Read field errors from `extra` only when it is an array.

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
      // Always show message; extra is a list of field errors or null
      throw new ValidationError(error.message, Array.isArray(error.extra) ? error.extra : []);
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
            # Always keep message; extra is a list of field errors or null
            fields = error["extra"] if isinstance(error.get("extra"), list) else []
            raise ValueError(f"Validation failed: {error['message']}", fields)
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
- **Retry with backoff on 5xx and 429 only** — other 4xx errors are client errors and won't resolve on retry. On 429, wait for the `Retry-After` header first.

## Rate Limits

Each client has one request budget shared by all public endpoints:

- **With an API key**, the budget belongs to the key's account.
- **Without one**, it belongs to your IP address, and it is much smaller. Send an API key for production traffic.

Going over the budget returns `429` with `error_name: "throttled"` and a `Retry-After` header that gives the number of seconds to wait:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 12
Content-Type: application/json

{"error_name": "throttled", "message": "Request was throttled. Too many requests.", "extra": null}
```

Wait at least `Retry-After` seconds before retrying.

## Custom Endpoint Errors

Some endpoints raise `ItqanError` for business-logic conditions (for example, a conflict or a domain validation failure). These produce a custom `error_name` specific to that endpoint. Each endpoint's API Reference page documents the custom error names it can return.

---

**See also:** [Design Principles](/docs/guides/api-design) · [API Reference](/docs/reference/api/) · [Authentication](/docs/getting-started/authentication)
