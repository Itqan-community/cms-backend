---
sidebar_position: 1
title: Design Principles
description: The conventions and design decisions behind the Fanar API surface.
---

# Design Principles

This page documents the design decisions behind the Fanar API. Understanding these principles helps you build integrations that are correct, maintainable, and ready for future expansion.

## REST and JSON

All endpoints follow REST conventions. Resources are plural nouns at predictable URL paths (`/reciters/`, `/recitations/`, `/riwayahs/`). Every response body is JSON with `Content-Type: application/json`. HTTP verbs carry their standard meaning: `GET` reads, `POST` creates, and so on.

## Stable Resource IDs

Every resource has an integer `id` field. These IDs are stable: once assigned, a reciter ID of `42` will always refer to that reciter. You can persist IDs in your database, embed them in URLs, and cite them across requests without worrying about them changing across API versions.

## Response Envelope

Paginated list endpoints wrap their payload in a consistent envelope:

```json
{
  "count": 150,
  "results": [...]
}
```

`count` is the total number of matching records (not just the current page). `results` holds the page of items. Single-resource endpoints return the object directly — no envelope wrapper.

See [Response Structure](/docs/guides/response-structure) for full details.

## Compact Related Resources

When a resource references another (a recitation references its publisher, reciter, riwayah, and qiraah), the API embeds a compact `{id, name}` object inline instead of a URL or a bare foreign key integer. This lets you render a complete list item — name, related names, counts — from a single request.

```json
{
  "id": 7,
  "name": "Hafs an Asim",
  "publisher": { "id": 3, "name": "Itqan" },
  "reciter": { "id": 12, "name": "Mishary Rashid Alafasy" },
  "riwayah": { "id": 1, "name": "Hafs" }
}
```

When you need the full record for a related resource, call its own endpoint using the embedded `id`.

See [Related Object Embeds](/docs/guides/related-resources) for the full pattern specification.

## Locale-Aware Fields

Fields that carry human-readable text — `name`, `description`, `bio` — return content in the language requested via the `Accept-Language` header. Send `Accept-Language: ar` for Arabic, `Accept-Language: en` for English. The JSON key is always the same (`name`, not `name_ar` or `name_en`); only the value changes.

See [Localization](/docs/guides/localization) for header usage and field coverage.

## Unified Error Envelope

All non-2xx responses share the same structure:

```json
{
  "error_name": "not_found",
  "message": "No asset matches the given query.",
  "extra": null
}
```

`error_name` is a stable, machine-readable identifier — switch your error handling on this, never on `message`. `message` is a human-readable, localized string suitable for display. `extra` carries optional structured detail (for example, field-level validation errors).

See [Error Handling](/docs/guides/errors) for the full error catalog.

## Caching

The list endpoints (`/recitations/`, `/reciters/`, `/riwayahs/`, `/packages/`, `/recommendations/trending/`, `/recommendations/editorial/` and `/recommendations/similar/{asset_id}/`) send `Cache-Control: public, max-age=60` and an `ETag`:

- A browser or CDN may reuse a list for up to 60 seconds, so a publisher's edit can take up to a minute to show.
- After that, send the `ETag` back in `If-None-Match`. When nothing changed you get `304 Not Modified` with an empty body, and you keep using your copy.
- Responses to a request with an API key are `private, max-age=60`: only your own client may keep them, never a shared cache.

```bash
curl -i {{API_BASE}}/reciters/ -H 'If-None-Match: "3f2a…"'
# HTTP/1.1 304 Not Modified
```

## Backwards-Compatible Evolution

The API evolves additively. These changes can ship at any time, without notice:

- new endpoints, new optional query parameters and new fields in existing responses
- new `error_name` values (treat an unknown one as a generic error)
- new values in enum-like fields

Your client must ignore unknown fields rather than fail on them. An integration built against `/recitations/` today keeps working as fields are added.

## Deprecation Policy

Paths are not versioned: there is no `/v1/` and none is planned. A breaking change (a removed or renamed field, endpoint or parameter, a changed type, status code or `error_name`) follows this policy instead:

1. **Notice.** The change is announced in these docs at least **90 days** before it takes effect.
2. **Headers.** During those 90 days the old behaviour keeps working, and every response it affects carries:
   - `Deprecation: @<unix-timestamp>`: when the old behaviour was deprecated ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745))
   - `Sunset: <HTTP-date>`: when it stops working ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594))
   - `Link: <docs page>; rel="deprecation"`: where the change is described
3. **The itqan CLI first.** A CLI release that handles the new behaviour ships before the old one is removed.
4. **Removal.** After the `Sunset` date the old behaviour is gone.

```http
HTTP/1.1 200 OK
Deprecation: @1798761600
Sunset: Mon, 01 Mar 2027 00:00:00 GMT
Link: <https://docs.example/docs/guides/api-design#deprecation-policy>; rel="deprecation"
```

CORS exposes all three headers, so browser code can read them. Log or alert on the `Deprecation` header in your client so you hear about a change before its sunset date. Security fixes, and fixes that make the API do what these docs already say, can ship without the 90-day window.

---

**See also:** [Response Structure](/docs/guides/response-structure) · [Related Object Embeds](/docs/guides/related-resources) · [Error Handling](/docs/guides/errors)
