---
id: index
title: API Reference
slug: /reference/api/
sidebar_label: Overview
sidebar_position: 0
hide_title: false
---

# API Reference

The Quranic CMS API is a REST API for Quranic recitation data — reciters, recitations, riwayat, qira'at, and ayah-level audio timings from verified publishers. Base URL: `{{API_BASE}}`.

## Quick links

| | |
|---|---|
| [Quickstart](/docs/getting-started/quickstart) | Make your first API call in under a minute |
| [API Guides](/docs/guides/api-design) | Design conventions, pagination, localization, and more |
| [Authentication](/docs/getting-started/authentication) | OAuth 2 token endpoints (for privileged operations) |

## Conventions

- **Response shape** — [Response Structure](/docs/guides/response-structure): all list endpoints return `{count, results}`.
- **Pagination** — [Pagination](/docs/guides/pagination): `page` and `page_size` params, default 20, max 1 000.
- **Localization** — [Localization](/docs/guides/localization): pass `Accept-Language: ar` for Arabic text in all name/bio fields.
- **Errors** — [Error Handling](/docs/guides/errors): every non-2xx response uses `{error_name, message, extra}`.

## Resource groups

**Reciters** — Verified Quran reciters with name, bio, and recitation count. Start with [List Reciters](/docs/reference/api/apps-content-api-public-reciters-list-reciters).

**Recitations** — Full recitation records linking a reciter, riwayah, qiraah, and publisher. Each includes surah-level track counts. Start with [List Recitations](/docs/reference/api/apps-content-api-public-recitation-list-list-recitations).

**Recitation Tracks** — Surah-level audio track entries for a given recitation, including ayah timings. Start with [List Recitation Tracks](/docs/reference/api/apps-content-api-public-recitation-track-list-list-recitation-tracks).

**Riwayahs** — Narration chains (e.g. Hafs an Asim, Warsh). Start with [List Riwayahs](/docs/reference/api/apps-content-api-public-riwayahs-list-riwayahs).

**Authentication** — Token issuance and revocation for authenticated operations. See the [Authentication guide](/docs/getting-started/authentication).
