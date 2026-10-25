# Multi-Column Text Assets — cms-frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editors see and edit every text column of a translation/tafsir. Permitted users manage columns. Translators get a "Show source" toggle. Commit forces a major bump after a reorder. Review shows which column changed. The gallery asset page shows a "File structure" preview.

**Architecture:** The AG Grid column set is built from the draft's `column_keys` plus the asset's column labels. Every text cell reads from and writes to `row.cells[key]` under column id `cell__<key>`. Source columns `source__<key>` are hidden until the toggle is on. Edits are tracked per `(unit_id, column)`. Column management is one modal, opened from the toolbar and from a ⚙ in each text column's header.

**Tech Stack:** Angular (signals, standalone components), ng-zorro-antd, AG Grid (infinite row model), ngx-translate, Karma (`ng test`).

**Spec:** `itqan-cms-backend-columns/docs/superpowers/specs/2026-10-21-multi-column-text-assets-design.md`
**Depends on:** backend plan Tasks 2, 4, 6, 7, 8 (endpoints and fields named below).

## Global Constraints

- Follow `cms-frontend/AGENTS.md`:
  - surgical edits, matching the existing style
  - no TODOs or placeholders
  - TDD with Karma specs
  - update `PROJECT_MAP.md`
  - before any commit: `npm run lint` (max-warnings 0), `npx prettier --check .` (it covers Markdown) and `npx tsc --noEmit -p tsconfig.app.json` (plain `npm run type-check` checks nothing)
- Work in a worktree: `git worktree add --no-track -b feat/multi-column-text-assets ../cms-frontend-columns origin/staging`.
- Every new UI string goes in `public/i18n/en.json` **and** `public/i18n/ar.json`, and layout must be RTL-safe.
- Backend contract (exact names):
  - Columns:
    - `GET/POST content/{category}/{slug}/columns/`
    - `PATCH/DELETE …/columns/{key}/`
    - `PUT …/columns/order/` with `{keys}`
    - each column: `AssetColumn{key, label_en, label_ar, order, committed}`
  - Entries:
    - `ContentEntry.cells: Record<string,string>`, `source_cells: Record<string,string> | null` (`text`/`source_text` still sent, as the first column)
    - patch row `{unit_id, column, text}`
    - filter-model keys `cell__<key>` / `source__<key>`
  - Versions:
    - `ContentDraftVersion.column_keys: string[]`, `requires_major: boolean`
  - Changes:
    - `ContentChange.column: string`, and the review change also has `column_label_en`/`column_label_ar`
  - Errors:
    - `major_bump_required`, `column_key_taken`, `column_key_invalid`, `column_committed`, `column_last`, `unknown_column`, `unknown_filter_column`
  - Gallery:
    - `GET cms-api/assets/{id}/file-structure/?language=` returns `{format, template, header: string[], columns: {key,label_en,label_ar}[], rows: string[][]}`, with a 404 `file_structure_unavailable`
- Permissions: column management UI shows only when the user has `PORTAL_MANAGE_ASSET_COLUMNS` (`'portal_manage_asset_columns'`) **and** `PORTAL_ACCESS_ALL_LANGUAGES`.
- A label is shown in the UI language (`label_ar` when `translate.currentLang === 'ar'`, else `label_en`), falling back to the other label, then to the key. The key is always shown as secondary text in headers.
- Verify in the user's Chrome via claude-in-chrome. Never install Playwright.

## Review Focus

1. **Editing two cells of the same row before autosave fires.** Both are saved, neither overwrites the other in the pending map, and undo reverts them in order. Pinned in Task 2.
2. **Saving a `requires_major` draft from a commit dialog opened before the reorder happened.** The `major_bump_required` error switches the dialog to major and explains why, rather than showing a red toast. Pinned in Task 4.
3. **A filter on a column that another tab just deleted.** A 400 `unknown_filter_column` clears that filter and reloads columns, with no stuck spinner. Pinned in Task 2.
4. **Arabic UI with English column labels, or the reverse.** The fallback chain gives a non-empty header, and pinned/flex columns lay out in RTL. Pinned in Task 2.
5. **Gallery language switch.** The preview follows the download language, and a 404 for an unavailable language hides the section without an error toast. Pinned in Task 6.

---

### Task 1: Models, services, permission constant

**Files:**
- Modify: `src/app/features/admin/models/asset-content.models.ts`, `src/app/features/admin/models/asset-review.models.ts`, `src/app/features/admin/services/asset-content.service.ts`, `src/app/features/admin/constants/portal-permission.constants.ts`
- Create: `src/app/features/admin/utils/column-label.util.ts` (+ spec)
- Test: `src/app/features/admin/services/asset-content.service.spec.ts` (extend or create)

**Interfaces:**
- Produces:
  - `interface AssetColumn { key: string; label_en: string; label_ar: string; order: number; committed: boolean }`
  - `ContentEntry` gains `cells: Record<string, string>` and `source_cells?: Record<string, string> | null`.
  - `ContentEntryPatch` becomes `{ unit_id: number; column: string; text: string }`.
  - `ContentDraftVersion` gains `column_keys: string[]` and `requires_major: boolean`.
  - `ContentChange` gains `column: string`, and the review change model gains `column`, `column_label_en`, `column_label_ar`.
  - `AssetContentService` methods:
    - `listColumns(kind, slug): Observable<AssetColumn[]>`
    - `createColumn(kind, slug, body: {key; label_en; label_ar}): Observable<AssetColumn>`
    - `updateColumn(kind, slug, key, body: Partial<{key; label_en; label_ar}>): Observable<AssetColumn>`
    - `reorderColumns(kind, slug, keys: string[]): Observable<AssetColumn[]>`
    - `deleteColumn(kind, slug, key): Observable<void>`
    - URLs are built with the existing `draftBase(kind, slug)` + `columns/…`, with `encodeURIComponent(key)`.
  - `PORTAL_PERMISSIONS.PORTAL_MANAGE_ASSET_COLUMNS = 'portal_manage_asset_columns'`
  - `columnLabel(column: {key; label_en; label_ar}, lang: string): string` gives the UI-language label, then the other label, then the key.
- [ ] **Step 1: Failing specs.**
  - `HttpTestingController` asserts each new method's verb, URL and body.
  - `columnLabel` covers ar/en/fallback/key-only.
- [ ] **Step 2:** `npx ng test --watch=false --include='**/asset-content.service.spec.ts' --include='**/column-label.util.spec.ts'` FAILS.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(content): column models and API client`.

---

### Task 2: Grid renders and edits every column

**Files:**
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.{ts,html,less}`
- Test: `asset-content-grid.component.spec.ts`, `asset-content-grid.datasource.spec.ts`

**Interfaces:**
- Consumes: Task 1.
- Produces, inside the component:
  - `columns = signal<AssetColumn[]>([])`, loaded with `listColumns` alongside the languages and reloaded after the modal (Task 3) closes with changes.
  - `columnKeys = computed(...)`: the draft's / viewed version's `column_keys` when present, else `columns()` order.
  - `showSource = signal(false)`, persisted per asset in `localStorage` under `content-grid:show-source:<slug>` and wrapped in try/catch.
  - `buildColumnDefs()`:
    - Replace the single `text` column with one per key: `colId: 'cell__' + key`, `valueGetter: p => p.data?.cells?.[key] ?? ''`, `valueSetter` writing `cells[key]` (and `text` when it's the first key).
    - The header is `columnLabel(...)` with the key as secondary text (header template, Task 3 adds the ⚙).
    - Keep the existing editor, popup, `cellClassRules` and text filter.
    - When editing a non-source language **and** `showSource()` is on, insert `source__<key>` read-only right before each `cell__<key>`. Use the same read-only popup setup the current `source_text` column has, reading `source_cells[key]`.
    - With the toggle off, there are no source columns.
    - The old `text`/`source_text` columns are removed.
  - `pendingRows` becomes `Map<string, ContentEntryPatch>` keyed `` `${unit_id}:${column}` ``. `CellEdit` gains `column: string`. `onCellValueChanged` reads the key from `event.colDef.colId`. `replay` and `applySavedRows` refresh `cell__<column>`.
  - "Show source" is an `nz-switch` in the toolbar, visible only when `!isEditingSource()`.
  - `copySelectedToCsv` header becomes `['label','reference_text', ...columnKeys()]`.
  - Datasource error handler: `unknown_filter_column` → `gridApi.setFilterModel(null)`, reload `columns`, rebuild the column defs, then refetch.
- [ ] **Step 1: Failing specs.**
  - With `column_keys ['question','answer']`, `buildColumnDefs()` has colIds `cell__question` and `cell__answer`, in that order and after `reference_text`.
  - When translating with `showSource` on, `source__question` comes before `cell__question`, and with it off neither source column exists.
  - Editing `question` then `answer` on the same row queues two patches `{unit_id, column}` (Review Focus 1). Undo twice restores both in reverse order.
  - The header is `label_ar` in `ar`, falls back to `label_en`, then to the key (Review Focus 4).
  - The datasource maps an `unknown_filter_column` 400 to clearing filters and refetching (Review Focus 3).
  - Copy CSV includes both keys.
- [ ] **Step 2–4:** FAIL → implement → PASS. Then run the whole grid spec files to confirm existing specs still pass.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(content): edit every text column in the grid`.

---

### Task 3: Manage columns (modal + header ⚙)

**Files:**
- Create: `src/app/features/admin/components/manage-columns-modal/manage-columns-modal.component.{ts,html,less,spec.ts}`
- Create: `src/app/features/admin/components/asset-content-grid/content-column-header.component.ts` (+ spec)
- Modify: `asset-content-grid.component.{ts,html}`

**Interfaces:**
- Produces:
  - `ManageColumnsModalComponent`
    - inputs: `kind`, `slug`, `columns: AssetColumn[]`, `focusKey: string | null`
    - output: `changed: void`
    - Lists columns in order, each with editable `label_en`/`label_ar`. The key is editable only when `!committed`.
    - Move up/down calls `reorderColumns`.
    - Delete is shown only when `!committed` and there's more than one column, behind an `nz-popconfirm` (not a browser dialog).
    - An "Add column" row takes key + labels. Keys are validated client-side with `/^[a-z][a-z0-9_]{0,63}$/`, and the server error is shown inline.
    - Error names map to `ADMIN.CONTENT_EDITOR.COLUMNS_MANAGE.ERRORS.<NAME>`.
    - When the asset has a committed version, a note tells the user that reordering means the next version will be major.
  - `ContentColumnHeaderComponent` (AG Grid `IHeaderAngularComp`)
    - Shows the label, then the key in a muted style, then a ⚙ button when `params.canManage`. The ⚙ calls `params.openManage(key)`.
    - It must keep AG Grid's sort/filter menu behaviour as it is today. Sorting is off, so render the menu button through `params.showColumnMenu` as AG Grid's default header does.
  - Grid:
    - `canManageColumns = computed(() => hasPermission(MANAGE) && hasPermission(ACCESS_ALL_LANGUAGES))`
    - a toolbar button `+ Add column` (only when `canManageColumns()` and not read-only) opens the modal with `focusKey=null`
    - on `changed`, reload `columns`, re-fetch the draft (for `column_keys`/`requires_major`) and rebuild the column defs
- [ ] **Step 1: Failing specs.**
  - The modal hides the key input and delete for a committed column.
  - Add calls `createColumn` and emits `changed`.
  - A `column_key_taken` error shows its translated message.
  - The header ⚙ is absent without permission.
  - The grid toolbar button is absent without either permission.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(content): manage asset columns`.

---

### Task 4: Commit dialog enforces a major bump after a reorder

**Files:**
- Modify: `asset-content-grid.component.{ts,html}` (commit dialog)
- Test: `asset-content-grid.component.spec.ts`

**Interfaces:**
- Produces:
  - `commitRequiresMajor = signal(false)`, set from the draft's `requires_major` when the dialog opens.
  - When it's true:
    - `commitBump` is forced to `'major'` and the minor option is disabled
    - the notice `ADMIN.CONTENT_EDITOR.COMMIT.MAJOR_REQUIRED_HINT` is shown
  - `showError('major_bump_required')` sets `commitRequiresMajor(true)` and `commitBump('major')`, keeps the dialog open, and shows the hint instead of a toast (Review Focus 2).
- [ ] **Step 1: Failing specs.**
  - With `requires_major: true`, the dialog opens with bump `major` and minor disabled.
  - A `major_bump_required` error response leaves the dialog visible with bump `major`, and `message.error` isn't called.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(content): require a major version after reordering columns`.

---

### Task 5: Show the column in diffs and review

**Files:**
- Modify: `src/app/features/admin/components/content-changes/content-changes.component.{ts,html}`, `src/app/features/admin/components/asset-review-grid/asset-review-grid.component.{ts,html}`
- Test: their specs

**Interfaces:**
- Produces:
  - Only when the asset has more than one column (any change's `column !== 'text'`, or the columns list has more than one entry), each change row shows a column chip after the unit label.
  - In review, the chip uses `columnLabel({key: column, label_en: column_label_en, label_ar: column_label_ar}, lang)`.
  - In the content-changes component, it uses labels from the grid's `columns()` passed as an input `columns: AssetColumn[]`.
  - Single-column assets look exactly as today.
- [ ] **Step 1: Failing specs.**
  - A two-column change list renders chips `Question` and `Answer`.
  - A single-column list renders no chip.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(review): show which column a change belongs to`.

---

### Task 6: Gallery "File structure" section

**Files:**
- Modify: `src/app/features/gallery/services/assets.service.ts`, `src/app/features/gallery/pages/asset-details/asset-details.page.{ts,html,less}`
- Create: model `AssetFileStructure` in the gallery models file that `AssetDetails` lives in
- Test: `asset-details.page.spec.ts` (create if absent), `assets.service.spec.ts`

**Interfaces:**
- Produces:
  - `AssetsService.getFileStructure(id: string, language: string | null): Observable<AssetFileStructure>` calls `GET ${BASE_URL}/assets/${id}/file-structure/` with a `language` param when it's set.
  - Page:
    - `fileStructure = signal<AssetFileStructure | null>(null)`, loaded for translation/tafsir only
    - loaded on init and whenever `selectedLanguage` changes, through an `effect` with `takeUntilDestroyed` that cancels stale requests via `switchMap`
    - a 404 sets it to `null` without a toast (Review Focus 5)
  - Template: a card in the main column titled `GALLERY.FILE_STRUCTURE.TITLE`.
    - A line `GALLERY.FILE_STRUCTURE.FORMAT` with params `{unit}`, e.g. "CSV · one row per ayah". `unit` comes from `GALLERY.FILE_STRUCTURE.UNITS.<TEMPLATE>`.
    - Then a table whose header cells show each `header` value. For text columns, `columnLabel` goes underneath.
    - Then up to 3 `rows`.
    - The cells' direction follows the content (`dir="auto"`).
- [ ] **Step 1: Failing specs.**
  - The service builds the URL with `?language=en`.
  - The page renders 4 header cells plus labels for a Q&A structure.
  - Changing `selectedLanguage` triggers a new request.
  - A 404 hides the card with no `message.error`.
  - A mushaf asset makes no request.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Run lint, prettier and type-check, then commit `feat(gallery): file structure preview for text assets`.

---

### Task 7: Translations, project map, browser check

- [ ] **Step 1:** Make sure every new key exists in both `public/i18n/en.json` and `public/i18n/ar.json`. Run a quick script: `node -e` that diffs the flattened key sets of the two files, and it must print nothing.
- [ ] **Step 2:** Update `PROJECT_MAP.md`: `[SYSTEM_FLOW]` (columns in the editor/review/gallery) and `[ARCHITECTURE]` (the new components). `[ORPHANS & PENDING]` must end up empty. Run `npx prettier --check .`.
- [ ] **Step 3:** Run `npm run lint`, `npx tsc --noEmit -p tsconfig.app.json`, then `npx ng test --watch=false`. All must be green.
- [ ] **Step 4: Browser check in Chrome (claude-in-chrome)** against a local backend on the backend branch. Record a GIF named `multi-column-editor.gif`. Steps:
  1. As a permitted user, add `answer` to a tafsir.
  2. Edit both cells.
  3. Commit.
  4. Reorder, and see the commit forced to major.
  5. Open an English rendition, toggle "Show source".
  6. Review, and see the column chips.
  7. Open the gallery page in `ar` and `en`, switch language, and see the preview follow.
  8. Log in as an editor without the permission, and see no ⚙ and no "+ Add column".
- [ ] **Step 5:** Commit `docs: project map for multi-column text assets`.
