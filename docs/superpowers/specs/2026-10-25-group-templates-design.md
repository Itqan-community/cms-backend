# Ayah-Group and Word-Group Templates for Tafsir — Design

**Date:** 2026-10-25
**Status:** Approved for planning
**Repos:** `itqan-cms-backend` (primary), `cms-frontend`, `itqan-cli` (copy only)
**Builds on:** [`2026-09-17-asset-templates-design.md`](./2026-09-17-asset-templates-design.md),
[`2026-10-21-multi-column-text-assets-design.md`](./2026-10-21-multi-column-text-assets-design.md)

## Problem

Every text asset today is keyed to exactly one canonical unit per row: a surah,
an ayah, a word or a mushaf page (`AssetTemplateChoice`, `AssetVersionEntry`'s
`entry_exactly_one_unit` constraint). Real tafsir does not always follow those
units:

- One passage of commentary often explains **several ayahs together**
  (e.g. 2:1–5).
- Some commentary explains **only part of an ayah**: a run of words
  (e.g. the first four words of 2:255).

Neither can be represented today without duplicating text across ayahs or
words.

## Intent

Let a tafsir publisher store each passage once, against the exact span of the
Quran it explains, and hand developers a file that says so plainly.

## Goals

1. Two new templates for **tafsir**: **ayah group** (`ayah_group`) and
   **word group** (`word_group`).
2. A row of a group asset covers a **contiguous range**:
   - ayah group: from `surah:ayah` to `surah:ayah`;
   - word group: from `surah:ayah:word` to `surah:ayah:word`.
3. Group boundaries are defined by the publisher, per asset. There is no fixed
   canonical unit list.
4. **Overlaps are allowed** (a passage on 2:1–5 and a separate note on 2:3).
   **Gaps are allowed** (as an ayah tafsir may leave ayahs blank today).
5. Publishers mostly **import a CSV**; they can also add, edit and delete groups
   in the portal grid.
6. Developers get the same delivery as today — one CSV per version via the
   gallery download and the `itqan` CLI — in a new, range-shaped file they
   handle on purpose.
7. Versioning, change history, review, publishing and multi-column text work
   for group assets as they do for the other templates.

## Non-goals

- **Translations.** Only tafsir gets the new templates for now, though nothing
  in the design should make extending to translations hard.
- **Backward compatibility with ayah-tafsir readers.** A group file is a new
  shape; we do not emit QUL-style per-ayah pointer rows.
- **A mushaf-style visual editor** (select words on rendered text, brackets in
  the margin). Considered and deferred; revisit if typing word ranges proves
  painful.
- **Converting existing assets** between templates. The template stays
  immutable after creation.
- **Per-ayah sample text** (`sample-data/tafsir/`) for group assets: like word
  and page assets today, `extract_verse_text` returns `None` for them.

## Anti-goals (failure even if it "works")

- A half-imported tafsir: an upload with some bad rows silently dropping them.
- Materialising per-ayah or per-word rows to fake a group.
- A group asset leaking a file shape that mixes per-unit and range rows.

## Prior art

QUL (Tarteel) keeps one entry per ayah: the first ayah of a group holds the text
plus `ayah_keys`, the others hold a pointer string (`"2:4": "2:3"`); SQLite
exports use `ayah_keys` / `group_ayah_key`. It has no partial-ayah support.
Rejected here because it cannot express word groups without per-word rows and
cannot express overlaps; developers handling a new shape on purpose was
explicitly accepted.

## Decisions

| Decision | Resolution |
| --- | --- |
| Template names | `ayah_group` ("Ayah-group based"), `word_group` ("Word-group based") |
| Categories | `tafsir` only. Creating a translation with a group template is rejected (`400`). |
| Row identity | The full range `(from, to)` within a column. Two rows with an identical range in the same column are rejected. |
| Overlaps / gaps | Both allowed, no warnings on import. |
| Range validity | `from <= to` in mushaf order; single-unit groups (`from == to`) allowed. |
| Crossing boundaries | Ayah groups may cross surahs; word groups may cross ayahs (and surahs). *(Claude's call — words have global ids, so no extra rule is needed; restricting would add rules.)* |
| Ordering | By `from`, then `to` (longer passage after a shorter one starting at the same place). *(Claude's call)* |
| Boundary edits | Changing a group's range is recorded as **removed + added** in history/review; changing only text is **modified**. *(Claude's call)* |
| Word addressing in files | By position (`surah, ayah, word-in-ayah`), not our internal `Word.id`. *(Claude's call — publishers can read positions off any mushaf.)* |
| Import failure mode | Strict: any invalid row rejects the whole file with row numbers in the error. *(Claude's call)* |
| Editor | Option A: the existing content grid, one row per group (chosen by the user). *Amended 2026-10-26 (user):* ranges are edited in the table itself — typed start / end and ± buttons growing or shrinking the end by one ayah / word — plus an "add next group" button under the table; the range dialog remains for arbitrary ranges with the mushaf preview. |
| What makes a group exist | A committed range exists only while at least one text column has a non-blank cell for it. Cells are sparse: a group with text in some columns has no entries in the others, and adding a column adds no cells. Clearing a group's last text deletes the group at commit (recorded as **removed**). *Amended 2026-10-26 (user: edit groups in the table):* a draft may hold a blank group (added blank, or via "add next group") so it can be filled in the grid; committing drops it if still blank. This keeps round-trip exact (import already skips all-blank rows) and matches how missing cells already read as empty. *(Claude's call)* |
| Languages | **Translated languages use the source language's groups** (user's decision). Only the source language (`AssetLanguage.is_source`) can add, move or delete groups; a translated language only writes text against the source's ranges. See "Languages" below. |
| Word range visibility | **When a publisher picks a word range, the mushaf words of that range are shown on screen** (user's requirement), live as the from/to positions change. |
| Word numbering standard | The canonical `quran.Word` table (`position_in_ayah`) is the reference. Because a misnumbered file passes validation, publishers must be able to see what they attached: the range picker shows each word's text, the grid's Reference column shows the covered words, and the verbose export's `reference_text` column is **required**, not optional. *(Claude's call)* |

## File format

Delivered and imported as UTF-8 CSV, header-driven like the other templates.
Text columns follow the range headers, one per asset column key
(`resolved_column_keys`), exactly as multi-column assets work today.

**Ayah group**

```csv
from_surah,from_ayah,to_surah,to_ayah,text
2,1,2,5,"…commentary on 2:1–5…"
2,3,2,3,"…a separate note on 2:3…"
2,6,2,7,"…"
```

**Word group**

```csv
from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,text
2,255,1,2,255,4,"…commentary on the opening words of Ayat al-Kursi…"
```

- Rows are written sorted (see Ordering); input order does not matter.
- A row whose every text cell is blank is skipped on import (as today).
- An export imports back unchanged (round-trip), as today.
- The **blank template** download is the header row only — there is no unit
  list to enumerate.
- A **verbose** export (today: ayah template adds surah name + ayah text) adds a
  `reference_text` column with the covered Quran text for group templates. The
  importer ignores it, like the other verbose columns. Required for word groups
  (see Word numbering standard).
- The new range header names must be added to `UNIT_HEADERS` so a text column
  key cannot shadow them.

### Import validation (whole file rejected on any failure)

- Missing or unrecognised range headers for the asset's template.
- A position that does not exist (surah 1–114, ayah within surah, word within
  ayah).
- `to` before `from`.
- Two rows with the same range (for the same column — in practice the same row
  repeated).

Errors are `ItqanError`s with localized messages listing offending row numbers.
Upload imports for tafsir versions already run in strict mode.

## Backend

### Model

`AssetTemplateChoice` gains `AYAH_GROUP` and `WORD_GROUP`. The asset-level
constraints (`asset_template_required_for_text`, the page/mushaf-layout rule)
keep working: group templates need no `mushaf_layout`.

`AssetVersionEntry` and `AssetVersionChange` need to store a range. Direction
(the builder finalises naming and migration):

- Add nullable range columns: `from_ayah` / `to_ayah` (FK `quran.Ayah`) and
  `from_word` / `to_word` (FK `quran.Word`), `PROTECT`, `related_name="+"`.
  Do **not** reuse the existing `ayah` / `word` FKs as the start: the existing
  `unique (version, ayah, column)` constraints would forbid two overlapping
  groups that start at the same ayah.
- Extend `entry_exactly_one_unit` / `change_exactly_one_unit` with two more
  branches: exactly the ayah pair set, or exactly the word pair set, with every
  other unit column null.
- Add `unique (version, from_ayah, to_ayah, column)` and
  `unique (version, from_word, to_word, column)` (entries and changes).
- `from <= to` can be a DB check (`from_ayah_id <= to_ayah_id`; `Ayah.id` and
  `Word.id` are in mushaf order) or service-level validation; builder's choice,
  DB check preferred.
- `order` = the `from` unit's id (ties broken by `to` at query time).

### Unit identity

Today every pipeline keys a cell by `(unit_id: int, column_key)`
(`unit_id` property, `Snapshot`, `_entries_map`, diff, reconstruct, export).
Group rows need a composite key `(from_id, to_id)`. The builder decides the
representation (e.g. a small `UnitKey` value type used by all templates, or a
tuple for groups only) but the whole pipeline — entries endpoint, patch path,
diff, change recording, snapshot reconstruction, CSV export/import, review —
must use it consistently. Keep `asset_templates.py` the single place that
branches on template (its module docstring states this rule).

### `UnitSpec` for groups

Group templates have no canonical unit set. Their spec:

- **Lists stored rows**, not canonical units: `units_page` pages over the
  version's entries (distinct ranges across columns), sorted by `from`, `to`.
  `total` is the number of distinct ranges in the version.
- Label: `2:1 → 2:5` / `2:255:1 → 2:255:4` (single-unit: `2:3`).
- `reference_text`: the covered Quran text (ayah texts joined, or the words'
  text). For long ranges, the builder may truncate for the grid.
- `sura` / `aya` filter on the `from` position. *(Claude's call)*
- `valid_unit_ids` becomes "valid ranges": both ends exist and `from <= to`.

### Portal API

- Tafsir create accepts the two new templates; translation create rejects them
  (`template_not_allowed_for_category` or the existing equivalent).
- Entries endpoint returns group rows with their range (`from`/`to` structured,
  plus the label).
- New write operations on a draft: **add group** (range + cells), **change a
  group's range**, **delete group**. The existing cell patch edits text by group
  key. All writes go through Service → Repository and the existing draft
  locking (`lock_version_for_content_change`).
- Duplicate-range and invalid-range writes return `400` with typed
  `error_name`s.

### Languages

Tafsir assets can have several languages (`AssetLanguage`); versions, drafts
and review are per language. Group ranges belong to the **source language**:

- **Row set.** For the source language, the grid's rows are its own stored
  ranges. For a translated language, the rows are the ranges of the source
  language's current head version (newest committed, as the source overlay uses
  today), with the translation's text left-joined by range — the same
  "every unit listed, sparse text" shape the ayah template has. No seeding of
  empty rows is needed (a group exists only while it has text, and the row set
  comes from the source).
- **Source overlay.** The grid's source column (`_resolve_source_cells`,
  `source_cells`) matches by range.
- **Writes.** Add / change range / delete group endpoints are refused on a
  non-source language (`400`, typed `error_name`). Text writes on a
  non-source language must name a range that exists in the source head.
- **Import.** A translated language's CSV must use only ranges present in the
  source head; any other range rejects the file (strict, with row numbers).
  Source ranges missing from the file are simply untranslated (a gap).
- **Source changes after translation.** If the source later moves or deletes a
  group, the translation's text for the old range becomes **orphaned**. The
  grid lists orphaned rows (marked, read-only text, deletable) so the publisher
  can move the text to the new range; committing a translation version is
  refused while it still holds orphaned ranges, naming them. *(Claude's call —
  keeps every published translation aligned with its source without silently
  dropping text.)*
- **Ayah-template seeding** (`create_draft_seeded_from` /
  `ensure_mushaf_coverage`, gated on `template == AYAH`) stays as is and is not
  applied to group templates.

### History and review

`AssetVersionChange` rows carry the range. Diff between versions matches rows
by `(range, column)`: same range + different text → `modified`; range only in
the new version → `added`; only in the old → `removed`. A boundary edit thus
appears as one removed + one added, and each is reviewed individually as today.

### Consumer surfaces

The change does not alter any access/publishing rule, so the
"Publishing and asset availability" checklist only needs a confirmation pass.
Surfaces that serialize content must handle the new shape:

- `store_generated_package_file` (CLI + gallery downloads) — via the CSV export.
- `asset_file_structure` (gallery "what the file looks like") — header and
  first rows of the range shape; `template` returns the new value.
- `extract_verse_text` / `sample-data/tafsir/` — returns `None` for group
  templates (already the case for non-ayah templates; add a test).
- `get_ready_asset` (`apps/content/repositories/tafsir.py`) already picks only
  ayah-template tafsirs, so group assets are never sampled.

### Docs

Update `docs/ARCHITECTURE.md` (templates, entry/change model, ER diagram),
`docs/PACKAGE_ARTIFACT.md` where it assumes per-ayah entries, and the
`docs-website` page that describes the download format if one covers tafsir
CSV shape. Arabic translations for every new string (`msgfmt --check`, 0
untranslated).

## Frontend (`cms-frontend`)

- **Create form** (`tafsir-form`): the two new templates in the template
  picker, with their labels.
- **Template badge** wherever the template is shown.
- **Content grid** (`asset-content-grid`), option A:
  - One row per group. Columns: **Range** (editable), **Ayahs/Words** count
    *(Claude's call; optional)*, **Reference** (covered text, RTL), one column
    per text column key, and a delete action.
  - **Range editor**: from/to pickers — surah + ayah (ayah group) or
    surah + ayah + word (word group). Invalid or duplicate ranges show the API
    error inline.
  - **Mushaf words while picking** (required): while a word range is being
    picked, the covered mushaf words are shown on screen (RTL, Uthmani text),
    updating live as either end changes; words just outside the range may be
    shown dimmed for context. The same preview for ayah ranges (covered ayah
    text) is recommended. Needs a portal read endpoint returning the words /
    ayahs for a range (or reuse of an existing Quran text endpoint if one fits).
  - On a **translated language**, the Range column is read-only and "Add group"
    / delete are hidden; orphaned rows (see Languages) are marked.
  - **Add group** button in the toolbar opens a new row with an empty range.
  - Rows that overlap another row get a subtle marker with a tooltip naming
    the overlapped range. *(Claude's call)*
  - Upload / download CSV unchanged in placement; blank template is header-only.
  - The surah filter filters by the group's `from` surah.
- **Changes / review screens** (`content-changes`): show the range label in
  place of the unit label; a boundary edit appears as remove + add.
- **Gallery file-structure** component renders the new header generically
  (check it does not assume `surah,ayah`).
- Follow `cms-frontend/AGENTS.md`; type-check with `-p tsconfig.app.json`;
  `npx prettier --check .` before pushing.

## `itqan-cli`

No code change expected: it downloads the file as-is and prints
`CSV, one row per <template>`. Check that the template string reads well
(`one row per ayah_group`); if not, map it to a friendly phrase.

## Testing

Per backend rules (pytest, AAA comments, `BaseTestCase`, `error_name` asserted
on 4xx, `patch.object`):

- Model constraints: exactly-one-unit with ranges, duplicate range rejected,
  overlapping ranges accepted, `from > to` rejected.
- Import: happy path both templates, every rejection case with row numbers,
  overlap and gap accepted, out-of-order input sorted, multi-column, round-trip.
- Export / package file / file-structure: header and row shape, sort order.
- Portal: create (tafsir allowed, translation rejected), add / change range /
  delete / edit text, permissions as for existing content edits.
- Languages: translated language lists the source's ranges; range writes
  refused on non-source; import with a non-source range rejected; orphaned
  rows listed and block commit; source overlay matched by range.
- Range preview endpoint returns the right words/ayahs, including ranges
  crossing ayah and surah boundaries.
- Diff/history/review: modified vs removed+added, reconstruction of pruned
  versions.
- Samples: group asset returns no verse text.
- Performance: query counts for the entries endpoint and export on a group
  asset of a few thousand rows must stay flat (no per-row queries), and the
  word-group reference text must not N+1.

## Left to the builder

- Exact column/constraint names and the migration.
- The unit-key representation across the pipeline.
- Truncation of long reference text in the grid.
- Exact `error_name` values (follow existing naming).
