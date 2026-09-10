---
sidebar_position: 8
title: Identifying Your App
description: Send your application's name and version so issues can be traced to a specific release.
---

# Identifying Your App

Tell us which build is calling, and a bug report stops being a guess.

## How It Works

Send two optional headers with your requests:

| Header | Example | Purpose |
|---|---|---|
| `X-Client-Name` | `quran-companion` | A stable identifier for your application |
| `X-Client-Version` | `2.4.1` | The version of your application making the call |

We record both alongside the request in our error tracking and usage analytics. When something breaks, we can see which of your releases the failing calls came from — and so can you, when you ask us. If a bug appeared in `2.4.1` but never in `2.4.0`, that shows up immediately instead of after a week of back-and-forth.

Both headers are optional and neither affects the response body, your rate limit, or authentication.

## Example

```bash
curl https://cms.itqan.dev/recitations/ \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "X-Client-Name: quran-companion" \
  -H "X-Client-Version: 2.4.1"
```

Set them once where you build your HTTP client, not per call:

```javascript
const client = axios.create({
  baseURL: 'https://cms.itqan.dev',
  headers: {
    'X-API-Key': process.env.ITQAN_API_KEY,
    'X-Client-Name': 'quran-companion',
    'X-Client-Version': APP_VERSION,
  },
});
```

```python
session = requests.Session()
session.headers.update({
    "X-API-Key": os.environ["ITQAN_API_KEY"],
    "X-Client-Name": "quran-companion",
    "X-Client-Version": __version__,
})
```

## Accepted Values

| Header | Max length | Allowed characters |
|---|---|---|
| `X-Client-Name` | 64 | `A-Z` `a-z` `0-9` `.` `_` `-` |
| `X-Client-Version` | 32 | `A-Z` `a-z` `0-9` `.` `_` `+` `-` |

Semantic version strings pass as-is, including pre-release and build metadata — `2.4.1`, `2.4.1-beta.3`, and `2.4.1+build.77` are all valid.

Keep `X-Client-Name` stable across releases. It identifies the application, not the build; changing it between versions makes the history unusable.

## When a Value Is Rejected

A malformed header never fails your request. The value is ignored and the response carries an `X-Itqan-Warning` header explaining why:

```http
HTTP/1.1 200 OK
X-Itqan-Warning: ignored malformed X-Client-Version header; expected at most 32 characters of A-Z a-z 0-9 . _ + -
```

The rest of the response is unaffected. Omitting the headers entirely produces no warning — not sending them is normal.

The most common cause is a version string with spaces or parentheses, such as `2.4.1 (nightly)`. Send `2.4.1-nightly` instead.

:::note
`X-Itqan-Warning` is a custom header rather than the standard `Warning` header, which [RFC 9111](https://www.rfc-editor.org/rfc/rfc9111#name-warning) deprecated. If you call the API from a browser, it is exposed via CORS so your JavaScript can read it.
:::
