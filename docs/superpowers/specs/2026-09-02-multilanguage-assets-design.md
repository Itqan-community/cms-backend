# Multi-language text assets — design

**Date:** 2026-09-02
**Status:** Approved (design); implementation not started
**Scope:** Backend (`itqan-cms-backend`) + Frontend (`cms-frontend`)

## Problem

Today a text-based asset (translation / tafsir) carries a single `Asset.language`
code. An Arabic tafsir and its Spanish translation are therefore two unrelated
assets. We want **one asset** (e.g. "Tabari Tafsir") to hold the original plus
many language renditions (the source Arabic + up to ~50 translations).

Requirements gathered:

- **Designated source + targets.** The asset has one original/source language
  (e.g. `ar`) that is the source of truth; other languages are translations of it.
- **Per-language versions & drafts.** Each language versions independently. The
  Spanish translator publishes Spanish v2 without touching Arabic or Portuguese.
  At most one draft per `(asset, language)`.
- **One language edited at a time.** Editing is always locked to a single target
  language. Editing the source edits it alone; editing a translation shows the
  source as a read-only reference on the left and the target editable on the right.
  Never two editable languages at once.
- **Consumer delivery is in scope this phase.** Gallery / API let a consumer pick
  and download a specific language.
- **Per-language authoring permissions are deferred** (a Spanish translator must
  not see Portuguese, etc.), but the model must leave a clean seam so no rework is
  needed later.

## Current state (what exists)

- `Asset` — `language = CharField(max_length=10)` (free-form code), `category`,
  `slug`, publisher, access/licensing fields.
- `AssetVersion` — `FK asset`, `state` (`draft`/`published`), `file_url`,
  `content_edited`, `created_by`. Constraint: **one draft per `asset`**
  (`unique_draft_version_per_asset`). `get_latest_version()` returns the latest
  *published* version.
- `AssetVersionEntry` — `FK version`, `FK ayah`, `text`, `order`. (Footnotes were
  removed in a prior change.) Per-ayah editable content.
- Portal editing lives in `apps/content/api/portal/asset_content.py` (+ service
  `asset_content.py`, repository `asset_content.py`, importer
  `asset_content_import.py`). One router serves both translations and tafsirs via a
  `{category}` path segment.
- Consumer download: `apps/content/api/internal/assets_download.py` serves
  `asset.get_latest_version().file_url` (one file per asset). Access checks +
  `UsageEvent` logging are asset-level.
- `language` is a free-form string everywhere; there is **no** language vocabulary
  table or enum.

## Chosen approach

**Approach B — `AssetLanguage` registry + language-tagged versions.** Introduce a
first-class row per language an asset supports, and tag each `AssetVersion` with its
language. Rejected: Approach A (only add `language` to `AssetVersion`) — the set of
languages would be implicit and there would be no anchor for the deferred
per-language permissions or the consumer language list.

## Data model

### `Asset` (unchanged field, new meaning)

Keep `Asset.language` as-is; it now denotes the **source language**. No rename
(renaming churns `translations.py`, `tafsirs.py`, `mushafs.py`, `fonts.py`
create/list/filter code for no functional gain). The source language is also
represented as the `is_source=True` row in `AssetLanguage`, and the two must agree.

### `AssetLanguage` (new)

```
asset        FK -> Asset (related_name="languages", on_delete=CASCADE)
language     CharField(max_length=10)     # "ar", "es", "pt", ...
is_source    BooleanField(default=False)
+ BaseModel timestamps

Meta.constraints:
  UniqueConstraint(fields=["asset", "language"],
                   name="unique_language_per_asset")
  UniqueConstraint(fields=["asset"], condition=Q(is_source=True),
                   name="unique_source_language_per_asset")
```

Intentionally minimal (YAGNI) — no display label; the frontend maps code → name.
This is the anchor for the language switcher, the consumer language list, and (later)
per-language permissions / translator assignment.

### `AssetVersion` (add language scoping)

- Keep `asset` FK exactly as-is (all existing `version.asset` call sites keep
  working — no churn).
- Add `asset_language = FK -> AssetLanguage (on_delete=PROTECT)`.
- Enforce invariant `asset_id == asset_language.asset_id` in `save()`.
- Replace the draft constraint:
  - remove `unique_draft_version_per_asset`
  - add `UniqueConstraint(fields=["asset", "asset_language"],
    condition=Q(state=DRAFT), name="unique_draft_version_per_asset_language")`
- `get_latest_version(language=None)` — filter published versions by language;
  `None` falls back to the asset's source language.

### `AssetVersionEntry` (unchanged)

Entries hang off a version, which is now language-scoped, so per-ayah text is
automatically per-language. `unique(version, ayah)` stays.

### Resulting shape

```
Asset
 └── AssetLanguage (one per supported language; one is_source)
      └── AssetVersion (independent draft+published timeline per language)
           └── AssetVersionEntry (per-ayah text)
```

## Editor UX (portal, cms-frontend)

- **Language switcher** at the top of the content editor. Opening an asset lists its
  `AssetLanguage`s + an "Add language" action. The grid is always scoped to exactly
  one selected target language.
- **Two modes:**
  - *Editing the source* (target is `is_source`): single editable grid, no reference
    pane — columns `sura | aya | uthmani | text`.
  - *Editing a translation*: source's **latest published** text shown read-only on
    the left, target `text` editable on the right — columns
    `sura | aya | uthmani | <source> (read-only) | <target> (editable)`.
    Rationale: an unfinished source draft must not leak into translators' reference.
- **Add a target language:** curated ISO-639 dropdown in the picker, stored as the
  same free-form code string used elsewhere. Creating it makes the `AssetLanguage`
  row and opens its editor seeded with all source ayahs read-only on the left and
  empty target cells. Bulk-seed by uploading a CSV for that language (reuses the
  existing import path, now language-tagged). Sparse coverage stays allowed.
- **Everything else reuses existing machinery**, now operating within the selected
  language: per-`(asset, language)` draft lifecycle, autosave, undo/redo, copy/paste
  CSV, per-version download, smart version naming, no-changes-to-publish guard,
  abandoned-draft cleanup.

## Consumer delivery (internal API + gallery)

- `asset.get_latest_version(language)` — latest *published* version of that language;
  no language → source language (backward compatible).
- **Download** `assets/{id}/download/` gains optional `?language=xx`:
  - given → that language's latest published version's `file_url`
  - omitted → source language (today's behavior)
  - unknown/absent for the asset → `404 language_not_available`
- **Asset detail** (internal API feeding the gallery) grows `available_languages`
  from `AssetLanguage`, filtered to languages that have **at least one published
  version** (draft-only languages are hidden). Gallery renders a language switcher
  that re-points the download button at `?language=xx`.
- **Access / usage / licensing unchanged and asset-level:** a consumer with access
  to the asset gets all its languages. `UsageEvent` metadata gains the downloaded
  language for analytics. (Per-language gating is an authoring concern, deferred.)

## Permissions-readiness (deferred — build nothing now)

The shape leaves a clean seam so the deferred work is additive:
- `AssetLanguage` is the anchor a future `AssetLanguageAssignment`
  (user/role ↔ `AssetLanguage`) will FK to.
- The editor's language-list endpoint is the single choke point that will later
  filter by "languages you're assigned to."
- Category-level `PORTAL_UPDATE_TRANSLATION` / `PORTAL_UPDATE_TAFSIR` checks stay as
  they are; per-language gating layers on top later.

When permissions arrive: one model + one queryset filter, no schema rework.

## Migration & backfill

1. **Schema migration** — create `AssetLanguage`; add `AssetVersion.asset_language`
   (nullable at first); create the new draft constraint.
2. **Data migration** — for each existing `Asset`: create one
   `AssetLanguage(asset, language=asset.language, is_source=True)`; set every existing
   `AssetVersion.asset_language` to that row.
3. **Tighten** — make `AssetVersion.asset_language` non-null; drop
   `unique_draft_version_per_asset`, add `unique_draft_version_per_asset_language`.

Result: existing assets become one-language (source-only) assets; versions, entries,
gallery listings, and downloads are unchanged. New languages are purely additive.

## Testing

- **Model/migration:** backfill creates exactly one `is_source` `AssetLanguage` per
  asset and repoints versions; source-uniqueness and per-`(asset, language)` draft
  uniqueness enforced; `save()` invariant holds.
- **Portal:** add a language; drafts independent per language (publishing `es` leaves
  `ar`/`pt` untouched); translation editor returns source reference rows; source
  editor omits the reference; import/export are language-scoped; the shared
  get-or-create draft is now per `(asset, language)`.
- **Consumer:** `download?language=es` serves the `es` file; omitted → source;
  unknown language → 404; a language with only a draft is excluded from
  `available_languages`.

## Out of scope (this phase)

- Per-language authoring permissions / translator assignment (design seam only).
- Merging today's separate single-language assets into one multi-language asset
  (backfill treats each existing asset as source-only; consolidation is manual/later).
- Multi-language for non-text categories (mushaf, recitation, fonts) beyond the
  existing single `Asset.language`.
