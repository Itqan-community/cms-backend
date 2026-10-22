# Multi-Column Text Assets — Design

**Date:** 2026-10-21
**Status:** Draft, pending user approval
**Repos:** `itqan-cms-backend` (primary), `cms-frontend`, `itqan-cli`

## Intent

Translations and tafsirs hold one text per unit today (`AssetVersionEntry.text`).
Some useful datasets need several texts per unit:

- **Question and answer per ayah.** App developers show the question, then
  reveal the answer, or they use the pairs as training data.
- **Comparison.** One asset puts several sources' commentary on the same
  ayah side by side, one column per source.

This feature lets a text asset carry any number of named text columns. Every
column gets the same treatment `text` gets now: editing, search/filtering,
drafts, versioning, diffs, reviews, translation into other languages, CSV
import/export and package downloads.

Very few people will create such assets, so adding and shaping columns sits
behind a new permission. Developers consuming the data must be able to tell an
asset's shape before downloading it, both in the gallery and in `itqan.yaml`.

## Goals

1. A translation/tafsir asset can have one or more text columns, each with a
   publisher-chosen **key**.
2. Users with the new permission can add columns to an asset at any time,
   set their labels, reorder them, and delete a column that was never
   published.
3. Ordinary content editors fill and translate cells in every column, the
   same way they edit `text` today.
4. Every column can be filtered/searched in the editor.
5. Translations of a multi-column asset have the same columns (same keys),
   with translated cells.
6. The gallery asset page shows a "File structure" preview: the format, the
   column keys and labels, and the first few rows.
7. `itqan add` writes a comment block above the asset's `itqan.yaml` entry
   that describes its columns.

## Non-goals

- Letting `itqan` users install a subset of columns. Out of scope now, but
  the manifest format and APIs must not rule it out later (see CLI section).
- Typed columns (numbers, booleans, rich text). Every column is plain text,
  like `text` today.
- Columns for categories other than translation and tafsir.
- Per-language column sets. A rendition can't have a column the source lacks.
- More than one row per unit. One Q&A (or one multiple-choice item) per ayah
  is enough, as confirmed by the user. For example, multiple choice is modelled
  as `question, correct_answer, wrong_answer_1, wrong_answer_2,
  wrong_answer_3` in one row. Cells are plain text with no validation across
  columns.

## Anti-goals (failure even if it "works")

- **Breaking existing consumers.** Every existing asset, file, API response
  and `itqan.yaml` must look exactly as it does today. Single-column assets
  keep the CSV header `text`.
- **A published file changing shape under a developer.** A published version's
  columns are frozen. A column that has appeared in a published version can
  never be removed or re-keyed.
- **Keys that differ by language.** Developers must be able to read
  `row["question"]` from the Arabic and English files alike, with no
  per-language mapping.
- **Regressing editor or download performance for single-column assets.**
  Measure query counts and hot paths against `staging` (see the project's
  performance rule).

## Decisions (settled with the user)

| Decision | Resolution |
| --- | --- |
| Shape | Any number of arbitrary, publisher-named columns per asset |
| Column key | Set at creation and **immutable once published**. It is the CSV header and API field name |
| Key across languages | Identical in every language rendition |
| Column set ownership | Per asset. Every language and every version of the asset uses the asset's column set as it stood when that version was made |
| Adding a column | Allowed at any time. It appears in the draft / next version, and already published versions are untouched |
| Removing a column | Only while it has never been in a published version. Afterwards it is permanent, and publishers can only leave it empty |
| Who manages columns | Users with a new permission (create/label/reorder/delete-unpublished) |
| Who edits cells | Anyone with today's tafsir/translation content-edit permission, in every column |
| Gallery indication | Option **B**: a "File structure" section on the asset details page showing a sample of the first rows with the column keys and labels |
| Translation editor layout | Option **C**: all target-language columns are shown, source columns are hidden by default, and a toggle shows each source column beside its translation |
| itqan-cli indication | A comment block **above the asset's entry in `itqan.yaml`**, not a preamble inside the downloaded CSV |
| Subset selection in CLI | Future, not now |
| Column changes and versioning | Adding a column is a **minor** change (additive; key-based readers are unaffected). Reordering columns that appear in a committed version **forces a major** bump, and the commit dialog explains why |
| Preview visibility | Everyone who can open the asset page sees the "File structure" preview, column names **and** sample rows, capped at about 3 rows. No access grant is needed, in line with public samples |

## Calls made during brainstorming (user may override)

These were proposed by Claude and not objected to. They are flagged so the
user can check them while reading.

1. **Display labels.** Besides the fixed key, each column has optional
   display labels in Arabic and English (the CMS UI languages, via
   modeltranslation like other bilingual fields). UI surfaces show the label
   in the viewer's UI language, falling back to the key. Labels can be edited
   at any time, but files and APIs never contain them, except the manifest
   comment (see CLI).
2. **Existing assets.** Every existing translation/tafsir has exactly one
   column keyed `text`. Nobody sees a migration happen.
3. **New multi-column assets.** A user with the permission names every
   column, including the first, so a Q&A asset is `question,answer`, not
   `text,answer`. The first column's key can be changed only while the asset
   has never published a version.
4. **Column order** can be changed at any time and controls the order in the
   CSV, the editor, the preview and the manifest comment. A published file
   keeps the order it was built with.
5. **"File structure" preview shows on every translation/tafsir**,
   single-column ones included (`sura, aya, text`), because the format note
   helps everyone.
6. **Manifest comment refresh.** The comment describes the resolved version.
   When `itqan update` (or install) resolves a version whose columns differ,
   the CLI rewrites **only its own** comment block, identified by a marker,
   and never touches comments the developer wrote.
7. **Single-column assets get no manifest comment**, so today's manifests
   don't change.
8. **When a column locks.** A column can't be deleted or re-keyed once any
   **committed** version (`state=PUBLISHED`) contains it, not only explicitly
   published or served ones. `itqan` can install committed, approved versions
   (`_released_version_ids`), so this is the only reading that keeps
   installable files stable. It also means deleting a column never cuts into
   committed history, so delta replay in `reconstruct_entries` stays sound.
9. **Rollback and restore.** Rolling back the served version to an older one
   is allowed and serves that version's own column set. Restore creates a new
   head with the asset's **current** columns, filling columns added after the
   restored version with blanks. It never removes a column.
10. **CSV upload must carry every column.** *(Revised during planning.)*
    An upload creates or replaces a whole version, and that version is
    diffed against its predecessor. A column absent from the file would read
    as "every cell removed". So a multi-column upload must have a header for
    every column key, or it fails with `content_file_missing_columns`. Extra
    unknown headers are ignored, as today. The legacy text aliases
    (`translation`, `text`, `content`, `المحتوى`) apply only to
    single-column assets.
11. **Column-management permission scope.** It requires
    `PORTAL_MANAGE_ASSET_COLUMNS` **plus** all-languages access
    (`PORTAL_ACCESS_ALL_LANGUAGES`), because a column affects every language.
12. **Dependabot refreshes the comment block.** When the backend's manifest
    rewrite bumps an entry to a version with different columns, it rewrites
    the CLI-marked comment block the same way the CLI would. Both must
    produce identical text, so share the format via a documented spec.

## Current state (what the builder inherits)

- `AssetVersionEntry` (`apps/content/models.py`) has one row per
  `(version, unit)` with a single `text`. Unit is one of sura / ayah / word /
  page (`AssetTemplateChoice`), with unique constraints per
  `(version, <unit>)`.
- `AssetVersionChange` records `old_text`/`new_text` per unit.
  `AssetVersionChangeReview` reviews a change. Diffs and reviews are
  per-unit.
- `AssetContentRepository` (`apps/content/repositories/asset_content.py`)
  reconstructs a version as `{unit_id: text}` (`reconstruct_entries`), diffs
  maps (`diff_maps`), records changes (`_record_changes`,
  `record_upload_changes`), and writes CSVs (`_units_to_csv_bytes`) with
  headers such as `sura,aya,text` / `word_id,sura,aya,word,text` /
  `page,text` / `sura,text`.
- `asset_content_import.py` parses uploaded CSVs by header aliases
  (`_TEXT_HEADERS = translation/text/content/المحتوى`).
- Package downloads build the CSV on demand
  (`PackageRegistryRepository.store_generated_package_file`). The catalog
  for `itqan` lives in `apps/package_manager/`.
- AI translation (`apps/content/services/ai_translation.py`,
  `api/portal/ai_translate.py`) translates text cells.
- Public samples (`apps/content/api/public/samples.py`) expose
  `sample_verse.text`.
- Dependabot (`apps/dependabot/services/manifest_parse.py`,
  `manifest_update.py`) parses and rewrites `itqan.yaml`, and **rejects
  unknown entry fields**.
- Frontend editor: `cms-frontend/src/app/features/admin/components/asset-content-grid/`
  (AG Grid, server-side filters per column, `source_text` column when
  translating, undo/redo, copy-to-CSV, drafts/commit).
- Gallery details: `cms-frontend/src/app/features/gallery/pages/asset-details/`.
- CLI manifest writing: `itqan-cli/src/itqan_cli/init_template.py`
  (`entry_lines`), `add.py`, `manifest.py`.
- Permissions: `apps/core/permissions.py` (`PermissionChoice`,
  `PERMISSION_IMPLICATIONS`).

## Design

### Data model (backend)

- New model **`AssetColumn`**: `asset` FK, `key` (slug-like, unique per
  asset), `label` (modeltranslation `label_ar`/`label_en`, optional),
  `order`. History-tracked like its neighbours.
- A column is **"published"** once any `AssetVersion` that is or was a
  published version of any language contains it. Before then it can be
  deleted, and its key can be changed if it is the first column of a
  never-published asset.
- Entries and changes become per **cell**: `AssetVersionEntry` and
  `AssetVersionChange` gain a `column` FK. Uniqueness becomes
  `(version, unit, column)`. Reviews stay attached to changes, so they are
  per cell automatically.
- Each version records which columns (and order) it was built with, so a
  published version's file shape is reproducible after columns are added or
  reordered. The storage choice is left to the builder, e.g. a M2M with
  order, or an ordered key list on `AssetVersion`.
- Backfill: every existing translation/tafsir gets one `AssetColumn(key="text")`.
  Existing entries and changes point at it. **Builder's call** whether to
  backfill the FK on all rows or treat a NULL column as the asset's `text`
  column. Pick the one that doesn't risk a long lock on production-size
  entry tables, and measure.
- Snapshots become `{(unit_id, column_id): text}` (or equivalent). Diffs,
  change recording, CSV export and reconstruction work per cell.

### Versioning
- When committing, compare the new version's column order with the
  predecessor's. If committed columns were reordered, force a major bump and
  have the commit dialog explain why. Adding columns leaves the default minor
  bump alone.

### Permission

- New `PermissionChoice` (suggested name `PORTAL_MANAGE_ASSET_COLUMNS`) that
  gates column create / label edit / reorder / delete, together with
  all-languages access (call 11). It should imply read on
  tafsir and translation. Grant it through the existing role system. Only a
  few users will have it.
- Cell editing needs only today's `PORTAL_EDIT_TAFSIR_CONTENT` /
  `PORTAL_EDIT_TRANSLATION_CONTENT`.
- Users without the permission never see column-management UI. They see and
  edit whatever columns exist.

### Portal API

- CRUD for an asset's columns (list, create, update label/order, delete
  unpublished), with typed errors (`column_key_taken`,
  `column_key_invalid`, `column_published`, …), all with localized messages
  and Arabic translations per the backend localization gate.
- Entries endpoints return and accept cells per column. Server-side filters
  work per column, the same as `text` today.
- Diff/change/review endpoints identify the column of each change.
- Upload/import: CSV headers matching column keys fill those columns. For
  single-column assets the existing aliases keep working unchanged. Unknown
  headers are handled as today. The blank fill-in template lists every
  column.
- AI translate is out of scope: it translates asset metadata only, never
  cell text (`apps/content/services/ai_translation.py`).

### Consumer surfaces (follow the "Publishing and asset availability" rule)

- **CSV files** (gallery download and package registry): the unit columns,
  then one column per text column in order, headed by keys. Single-column
  assets stay byte-identical to today.
- **Gallery asset details API** (`apps/content/api/internal/`): add the
  column list (key, label) and a small preview (first few rows of the
  selected language's published version) for the "File structure" section.
  Reuse the existing published-version rules, and return no preview when
  nothing is visible. Preview rows are visible without an access grant,
  capped at about 3 rows.
- **Package catalog** (`/packages/`): each language exposes its resolved
  version's columns (key, labels) so the CLI can describe them without
  downloading.
- **Public samples**: no change. `extract_verse_text` reads only JSON
  version files, and editor-produced versions are CSV.
- Tenant and other public APIs that expose entry text: keep `text` as the
  first column for compatibility, and expose all columns in a way that
  matches whatever the samples choice is.

### Frontend

- **Editor (source rendition):** one grid column per text column, each with
  the existing server-side filter, editable like `text`. Users with the
  permission get "+ Add column" in the toolbar (key + optional ar/en labels)
  and a ⚙ menu on each column header (edit labels, move, delete if
  unpublished). Headers show the label, with the key visible as secondary
  text.
- **Editor (translating):** option C. All target-language columns are shown,
  plus a toggle "Show source" that inserts each source column (read-only)
  beside its translation.
- **Review/diff views:** each change shows which column it belongs to.
- **Gallery asset details:** option B. A "File structure" section on the
  main page with format ("CSV · one row per ayah" etc.) and a small table:
  header cells show key with the label underneath, followed by the first rows
  of the selected download language. It updates when the download language
  changes.
- All new strings in English and Arabic, RTL-safe. Follow
  `cms-frontend/AGENTS.md`.

### itqan-cli

- `itqan add` writes a marked comment block above a multi-column entry:

  ```yaml
  assets:
    # itqan: ayah-qa · CSV · one row per ayah
    # itqan: columns: sura, aya, question, answer
    # itqan:   question — Question / السؤال
    # itqan:   answer — Answer / الجواب
    ayah-qa:
      version: "^1.2.0"
  ```

  The exact wording and marker are the builder's call (Dependabot must render
  it identically, see call 12). The marker must let the
  CLI find and replace only its own lines.
- `itqan install` / `update` refreshes that block when the resolved version's
  columns differ from what the block says.
- Single-column assets: no comment.
- **Dependabot compatibility:** the backend's manifest rewrite keeps these
  comment blocks intact and refreshes them when columns change (call 12). If a future `columns:` entry field is added for
  subset selection, `manifest_parse.py`'s unknown-field rejection will need
  updating in the same change. That's a reminder for later, not work now.

## Testing expectations

- Backend: model constraints, column CRUD + permission gate, per-cell
  diff/review, import/export round-trip for every template with 1 and N
  columns, byte-identical CSV for existing single-column assets, published
  column immutability, each consumer surface (gallery, catalog, download,
  samples, tenant) per the availability rule. Use `BaseTestCase`. Name tests
  and structure them in AAA as the backend rules require.
- Query counts for editor entries, CSV generation and catalog, compared with
  `staging`.
- Frontend: grid columns render from column metadata, management UI hidden
  without the permission, source toggle, gallery preview.
- CLI: comment written on add, refreshed on update, user comments untouched,
  no comment for single-column assets.

## Left to the builder

- How a version records its column set.
- NULL-means-`text` vs full FK backfill (decide on lock/perf evidence).
- Key format rules (suggest lowercase `[a-z0-9_]`, unique per asset, not
  colliding with unit headers like `sura`, `aya`, `word`, `page`, `word_id`).
- Preview row count, and exact CLI comment wording/marker.
- Whether the public samples / tenant APIs add a `columns` map now.
- Order of delivery across the three repos (backend first is the natural
  order).
