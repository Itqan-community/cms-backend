---
sidebar_position: 1
title: Design Principles
description: The conventions and design decisions behind the Itqan CMS API surface.
---

# Design Principles

This page documents the design decisions behind the Itqan CMS API. Understanding these principles helps you build integrations that are correct, maintainable, and ready for future expansion.

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

## Backwards-Compatible Evolution

The API evolves additively. New fields may appear in existing responses at any time; your client must ignore unknown fields rather than failing on them. Breaking changes — removed fields, changed types, renamed endpoints — are always introduced on a new path segment. An integration built against `/recitations/` today will keep working as new fields are added.

---

**See also:** [Response Structure](/docs/guides/response-structure) · [Related Object Embeds](/docs/guides/related-resources) · [Error Handling](/docs/guides/errors)
