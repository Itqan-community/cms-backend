---
sidebar_position: 6
title: Ayah Text (Tafsirs & Translations)
description: Fetch several tafsirs, translations and other text assets for one ayah, or a short range, in one call.
---

# Ayah Text (Tafsirs & Translations)

`GET /ayahs/{ayah_key}/?assets=…` returns the text of several text assets (tafsirs, translations and any other tagged text asset) for one ayah in a single call.

```bash
curl -H "X-API-Key: $ITQAN_API_KEY" \
  "{{API_BASE}}/ayahs/2:255/?assets=tafsir-al-muyassar,saheeh-international"
```

## Parameters

| Parameter | In | Description |
|---|---|---|
| `ayah_key` | path | `surah:ayah`, e.g. `2:255`. |
| `assets` | query | **Required.** Slugs of the text assets to return, comma-separated (`?assets=a,b`) and/or repeated (`?assets=a&assets=b`). At most 20. Only these assets are returned, in this order; a repeated slug is returned once. |
| `to` | query | Optional last ayah number of a range in the same surah, e.g. `/ayahs/2:1/?assets=…&to=5` for 2:1–2:5. At most 50 ayahs. |

Asset slugs are the package names shown in the asset library and by `itqan browse`.

## Response

```json
{
  "surah_number": 2,
  "from_ayah": 255,
  "to_ayah": 255,
  "assets": [
    {
      "slug": "tafsir-al-muyassar",
      "name_en": "Al-Muyassar",
      "name_ar": "التفسير الميسر",
      "category": "text",
      "tags": ["tafsir"],
      "template": "ayah",
      "language": "ar",
      "version": "1.2",
      "columns": [{ "key": "text", "label_en": "Text", "label_ar": "النص" }],
      "rows": [
        {
          "start": { "ayah_key": "2:255", "word_position": null },
          "end": { "ayah_key": "2:255", "word_position": null },
          "cells": { "text": "…" }
        }
      ]
    }
  ]
}
```

- Each asset is served at its **published version** in its **source language** (`version`, `language`).
- `columns` lists the asset's text columns in file order; `cells` has one entry per column key (`""` when that cell is empty). Use the labels to title the columns.
- `rows` are the asset's units that cover the requested ayahs, in Quran order. An asset with no text for those ayahs is still returned, with `rows: []`.

### Rows by template

`template` says what one row is:

| `template` | One row per | `start` / `end` |
|---|---|---|
| `ayah` | ayah | the same ayah |
| `word` | word | the same word (`word_position` is its position in the ayah) |
| `ayah_group` | group of ayahs the publisher wrote one text for | the group's first and last ayah; it may start before or end after the requested ayahs |
| `word_group` | group of words | the group's first and last word |

Surah-based and page-based assets have no per-ayah unit and are rejected (`asset_not_ayah_based`).

## Access

The endpoint follows the same rules as the recitation endpoints:

- Open assets need no API key.
- Restricted assets need an API key (`X-API-Key`) whose owner holds an approved access request for **each** of them. Request access from the asset's page in the asset library.

Each call counts as usage of every asset it returns.

## Errors

Errors apply to the whole request. When an error is about specific assets, `extra.assets` lists their slugs:

```json
{
  "error_name": "access_denied",
  "message": "You don't have an approved access request for these assets.",
  "extra": { "assets": ["restricted-tafsir"] }
}
```

| HTTP | `error_name` | When |
|---|---|---|
| 400 | `assets_required` | `assets` is missing or empty |
| 400 | `too_many_assets` | more than 20 slugs |
| 400 | `invalid_ayah_range` | `to` is before the first ayah, past the end of the surah, or the range is longer than 50 ayahs |
| 400 | `asset_not_text` | a slug names an asset that is not a text asset (a recitation, mushaf, font, …) |
| 400 | `asset_not_ayah_based` | a slug names a surah- or page-based text asset |
| 401 | `authentication_required` | a restricted asset was requested without an API key |
| 403 | `access_denied` | the API key's owner has no approved, unexpired access to a restricted asset |
| 404 | `ayah_not_found` | the ayah key is malformed or the ayah does not exist |
| 404 | `asset_not_found` | a slug is unknown, or the asset is not offered through the API or has nothing published |

When several checks fail, the first in this order is returned: `asset_not_found`, `asset_not_text`, `asset_not_ayah_based`, `authentication_required`, `access_denied`.

## Caching

Responses made only of open assets are cacheable for 5 minutes (`Cache-Control: public, max-age=300`). A response with any restricted asset is `private, no-cache`. A newly published version can take up to 5 minutes to appear.
