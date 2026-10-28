# Ayah-Group / Word-Group Templates — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publishers can create a tafsir with the `ayah_group` / `word_group` template and edit its groups in the existing content grid: add, move and delete groups through a range picker that shows the covered mushaf text, edit group text as today, and see translated languages follow the source's groups.

**Architecture:** Option A from the spec — the existing AG Grid content editor, one row per group (rows come from the backend, keyed by an opaque `unit_id`). Range choice lives in one new modal component (`GroupRangeModalComponent`) used for both "add" and "move". The grid adds a toolbar button, an actions column and an orphan marker for group templates only; single-unit templates render exactly as before.

**Tech Stack:** Angular (standalone components, signals), ng-zorro-antd, AG Grid Community (infinite row model), ngx-translate, Karma/Jasmine.

**Spec:** `itqan-cms-backend-group-templates/docs/superpowers/specs/2026-10-25-group-templates-design.md`. **Backend contract:** `itqan-cms-backend-group-templates/docs/superpowers/plans/2026-10-25-group-templates-backend.md`, Task 7 (endpoints, schemas, `error_name`s). Execute this plan after (or against a running build of) the backend plan.

## Global Constraints

- Worktree: create `cms-frontend-group-templates` next to `cms-frontend` — `git -C /Users/Apple/Documents/projects/cms/cms-frontend fetch origin staging && git -C /Users/Apple/Documents/projects/cms/cms-frontend worktree add --no-track -b feat/group-templates ../cms-frontend-group-templates origin/staging`, then `npm ci` inside it. The main `cms-frontend` checkout has unrelated work in progress: never touch it.
- **No commits** unless the user asks (leave the work in the tree for review).
- Follow `cms-frontend/AGENTS.md`: surgical edits, match surrounding style, no placeholders/TODOs, update `PROJECT_MAP.md` (`[SYSTEM_FLOW]` / `[ARCHITECTURE]` for the group editor; `[ORPHANS & PENDING]` empty at the end).
- Every user-facing string goes through ngx-translate with both `public/i18n/en.json` and `public/i18n/ar.json` entries; `npm run check:i18n` passes.
- Labels exactly: `ADMIN.ASSET_TEMPLATE.AYAH_GROUP` = `"Ayah-group based"` / `"حسب مجموعات الآيات"`; `ADMIN.ASSET_TEMPLATE.WORD_GROUP` = `"Word-group based"` / `"حسب مجموعات الكلمات"` (the badge builds `ADMIN.ASSET_TEMPLATE.${template.toUpperCase()}`).
- Group templates appear only in the **tafsir** form, never the translation form.
- Verification commands (all must pass before reporting done): `npx ng test --watch=false --browsers=ChromeHeadless`, `npx tsc --noEmit -p tsconfig.app.json` (plain `npm run type-check` checks nothing), `npm run lint`, `npx prettier --check .`, `npm run check:i18n`.
- UI checks happen in the user's Chrome via claude-in-chrome against the local backend; never install Playwright.
- Performance: the range preview request is debounced (300 ms) and a newer request cancels the older one (`switchMap`); group actions refresh only the grid cache, never reload the page; no new request per grid row.

## Review Focus

1. **Opening the editor of a brand-new group tafsir with zero groups**: the grid must still build its columns (template from the draft, not from a first row) and show "Add group". → test in Task 4.
2. **Typing quickly in the range picker**: stale preview responses must never overwrite a newer one. → test in Task 3.
3. **A word range ending in the next ayah** (e.g. 2:5:3 → 2:6:2): accepted by the picker and previewed across both ayahs. → test in Task 3.
4. **A translator on a translated language**: no Add/Move/Delete except Delete on an orphaned row; orphan cells are read-only. → test in Task 4.
5. **Committing a translation that still has orphaned text**: the `orphaned_groups` error lists the group labels instead of a generic toast. → test in Task 4.

---

### Task 1: Models, service calls and translations

**Files:**
- Modify: `src/app/features/admin/models/asset-content.models.ts`
- Modify: `src/app/features/admin/services/asset-content.service.ts`
- Modify: `public/i18n/en.json`, `public/i18n/ar.json`
- Test: `src/app/features/admin/services/asset-content.service.spec.ts` (create if absent)

**Interfaces:**
- Produces (`asset-content.models.ts`):
  - `AssetTemplate = 'surah' | 'ayah' | 'word' | 'page' | 'ayah_group' | 'word_group'`
  - `GROUP_TEMPLATES: readonly AssetTemplate[] = ['ayah_group', 'word_group']` and `isGroupTemplate(t: AssetTemplate | null | undefined): boolean`
  - `QuranPosition { surah: number; ayah: number; word?: number | null }`
  - `ContentEntry` gains `group_from?: QuranPosition | null; group_to?: QuranPosition | null; orphaned?: boolean`
  - `ContentDraftVersion` gains `template?: AssetTemplate | null` (the backend already sends it)
  - `QuranRangeUnit { surah: number; ayah: number; word: number | null; text: string }`, `QuranRangeResponse { units: QuranRangeUnit[]; truncated: boolean }`
- Produces (`AssetContentService`):
  - `addGroup(kind, slug, versionId, start: QuranPosition, end: QuranPosition, cells: Record<string, string>): Observable<ContentEntry[]>` → `POST {versionBase}groups/` body `{ start, end, cells }`
  - `moveGroup(kind, slug, versionId, unitId: number, start: QuranPosition, end: QuranPosition): Observable<ContentEntry[]>` → `PUT {versionBase}groups/{unitId}/` body `{ start, end }`
  - `deleteGroup(kind, slug, versionId, unitId: number): Observable<void>` → `DELETE {versionBase}groups/{unitId}/`
  - `quranRange(start: QuranPosition, end: QuranPosition): Observable<QuranRangeResponse>` → `GET {ADMIN_API_BASE_URL}content/quran-range/` with `from_surah, from_ayah, to_surah, to_ayah` and, when both positions carry a word, `from_word, to_word`
- Produces (i18n): `ADMIN.ASSET_TEMPLATE.AYAH_GROUP`, `…WORD_GROUP`; `ADMIN.CONTENT_EDITOR.GROUPS.{ADD, MOVE, DELETE, DELETE_CONFIRM_TITLE, DELETE_CONFIRM_BODY, FROM, TO, SURAH, AYAH, WORD, PREVIEW, PREVIEW_TRUNCATED, TEXT_REQUIRED, ORPHANED, ORPHANED_HINT, ADD_TITLE, MOVE_TITLE, ACTIONS}`; `ADMIN.CONTENT_EDITOR.ERRORS.{GROUP_RANGE_INVALID, GROUP_EXISTS, GROUP_NOT_FOUND, GROUP_RANGES_SOURCE_ONLY, GROUP_NOT_IN_SOURCE, TEMPLATE_NOT_GROUPED, ORPHANED_GROUPS}` (`ORPHANED_GROUPS` takes `{{groups}}`). Write the English and Arabic copy; keep the tone of the neighbouring keys.

- [ ] **Step 1: Write the failing tests** (HttpTestingController): one per new service method asserting method, URL and body/params; `quranRange` without words sends no `from_word`/`to_word`; `isGroupTemplate('word_group') === true`, `isGroupTemplate('word') === false`.
- [ ] **Step 2: Run** `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/admin/services/asset-content.service.spec.ts'` → FAIL.
- [ ] **Step 3: Implement** the types, methods and i18n keys.
- [ ] **Step 4: Run** the same command → PASS; `npm run check:i18n` → PASS.

---

### Task 2: Template choice in the tafsir form

**Files:**
- Modify: `src/app/features/admin/tafsirs/components/tafsir-form/tafsir-form.component.html` (options ~line 216–232)
- Test: `src/app/features/admin/tafsirs/components/tafsir-form/tafsir-form.component.spec.ts`

**Interfaces:**
- Consumes: Task 1 (`AssetTemplate`, i18n keys).
- Produces: two more `nz-option`s (`ayah_group`, `word_group`) after `page`, labelled `ADMIN.ASSET_TEMPLATE.AYAH_GROUP` / `WORD_GROUP`. No layout control for them (the existing `template === 'page'` logic already clears it). `csv-template-download` needs no change (`ready` is true for non-page templates); the backend returns a header-only file.

- [ ] **Step 1: Write the failing tests:** `tafsir form where template select opened should list ayah_group and word_group`; `tafsir form where word_group chosen should not require a mushaf layout and should send template word_group` (assert the create body). Add one to `translation-form.component.spec.ts`: `translation form should not list group templates`.
- [ ] **Step 2: Run** the two spec files → the tafsir tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.

---

### Task 3: `GroupRangeModalComponent` — pick a range and see its mushaf text

**Files:**
- Create: `src/app/features/admin/components/group-range-modal/group-range-modal.component.ts` (+ `.html`, `.less`, `.spec.ts`)

**Interfaces:**
- Consumes: Task 1 (`QuranPosition`, `quranRange`, `SURAHS_METADATA` from `../../models/quran-metadata`).
- Produces: standalone component, selector `app-group-range-modal`, used inside the grid template:
  - Inputs: `visible = input(false)`, `template = input.required<AssetTemplate>()` (a group template), `mode = input<'add' | 'move'>('add')`, `initialStart = input<QuranPosition | null>(null)`, `initialEnd = input<QuranPosition | null>(null)`, `columnKeys = input<string[]>([])` (add mode: one textarea per text column, labelled with the column title passed in `columnTitles = input<Record<string, string>>({})`), `busy = input(false)`, `serverError = input<string | null>(null)` (translated message to show inline).
  - Outputs: `confirmed = output<{ start: QuranPosition; end: QuranPosition; cells: Record<string, string> }>()` (`cells` is `{}` in move mode), `cancelled = output<void>()`.
  - Behaviour:
    - From and To each have a surah `nz-select` (from `SURAHS_METADATA`, labelled with `surahLabel`), an ayah `nz-select` bounded by the surah's `ayahs`, and for `word_group` a word `nz-input-number` (min 1). Defaults: add → both 1:1(:1); move → the initial range.
    - **Live preview (spec requirement):** whenever both ends are complete, after a 300 ms debounce, call `quranRange(start, end)` through `switchMap` (a newer request cancels the older); render the returned units' text right-to-left in the Uthmani font used by the grid's reference column (`direction: rtl; font-family: serif`), word units joined by spaces with an ayah-end marker `۝` and the ayah number between ayahs; show `GROUPS.PREVIEW_TRUNCATED` when `truncated`. A `400 group_range_invalid` shows `ERRORS.GROUP_RANGE_INVALID` inline instead of the preview.
    - Confirm is disabled while the preview is loading, while it shows an error, while `busy()`, and in add mode until at least one textarea has non-blank text (`GROUPS.TEXT_REQUIRED` hint) — a group exists only once it has text.
    - `serverError()` (e.g. `GROUP_EXISTS` from the grid's POST) is shown above the buttons.

- [ ] **Step 1: Write the failing tests** (fakeAsync, `AssetContentService` spy):
  - `where both ends complete should request the preview once after the debounce`.
  - `where the range changes twice quickly should only render the newest preview` (first observable delayed, second immediate; assert rendered text is the second's).
  - `where word_group spans two ayahs should send word positions and render both ayahs` (2:5:3 → 2:6:2; units across ayah 5 and 6 rendered with the `۝` marker between).
  - `where preview returns group_range_invalid should show the inline error and disable confirm`.
  - `where add mode and all texts blank should disable confirm`.
  - `where confirmed in move mode should emit start, end and empty cells`.
  - `where surah changes should bound the ayah options to that surah's ayah count`.
- [ ] **Step 2: Run** `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/admin/components/group-range-modal/**/*.spec.ts'` → FAIL.
- [ ] **Step 3: Implement.** Stub `NzModalService` per the repo pattern if the component imports `NzModalModule` (specs must `overrideProvider` it).
- [ ] **Step 4: Run** → PASS.

---

### Task 4: Group editing in the content grid

**Files:**
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.ts`, `.html`, `.less`
- Test: `src/app/features/admin/components/asset-content-grid/asset-content-grid.groups.spec.ts` (new)

**Interfaces:**
- Consumes: Tasks 1 and 3.
- Produces (component):
  - `readonly isGroup = computed(() => isGroupTemplate(this.effectiveTemplate()))`.
  - `draftTemplate = signal<AssetTemplate | null>(null)` set from `draft.template` in `loadForLanguage` and from `version.template` in `loadViewedVersion`; `effectiveTemplate = computed(() => this.template() ?? this.derivedTemplate() ?? this.draftTemplate())` so an empty group asset still builds its columns.
  - `readonly canEditGroups = computed(() => this.isGroup() && this.isEditingSource() && !this.readOnly())`.
  - Group modal state: `groupModal = signal<{ mode: 'add' | 'move'; unitId: number | null; start: QuranPosition | null; end: QuranPosition | null } | null>(null)`, `groupBusy = signal(false)`, `groupError = signal<string | null>(null)`.
  - `openAddGroup()`, `openMoveGroup(row: ContentEntry)`, `confirmGroup(event)`, `confirmDeleteGroup(row: ContentEntry)`; each write first `await this.flushPending()`, then calls the service, then `this.gridApi?.refreshInfiniteCache()` and `this.refreshPendingCount()`; on error maps `error_name` to `ADMIN.CONTENT_EDITOR.ERRORS.*` into `groupError` (modal stays open) — delete errors go through `showError`.
  - `handleCommitError` handles `orphaned_groups`: `message.error(translate.instant('ADMIN.CONTENT_EDITOR.ERRORS.ORPHANED_GROUPS', { groups: err.error.extra.groups.join('، ' or ', ' by language) }))`.
- Column rules in `buildColumnDefs()` for a group template (single-unit templates unchanged):
  - Unit column (`label`, e.g. `2:1 → 2:5`) keeps the surah dropdown filter (the backend filters by the group's start surah); width 170.
  - No separate `sura` / `aya` columns.
  - `reference_text` column as for `ayah`, header `REFERENCE`.
  - Text columns as today, except cells of an `orphaned` row are not editable (`editable: (p) => !p.data?.orphaned`) and the row gets class `content-grid__row--orphaned` (`rowClassRules`) with the unit cell showing a tag `GROUPS.ORPHANED` and tooltip `GROUPS.ORPHANED_HINT`.
  - An actions column (`colId: 'group_actions'`, pinned to the end side, width 110, no filter) rendered when `canEditGroups()` (Move + Delete icon buttons) or, on a translated language, when the row is orphaned (Delete only). Use a small cell renderer class in the same folder (`group-actions-cell.component.ts`) receiving `{ onMove, onDelete, canMove }` params.
- Toolbar: an "Add group" button (`GROUPS.ADD`) next to the existing toolbar actions, shown when `canEditGroups()`; disabled while `loading() || saving() || publishing()`.
- Delete confirmation via `NzModalService.confirm` (`GROUPS.DELETE_CONFIRM_TITLE` / `_BODY`, danger OK).

- [ ] **Step 1: Write the failing tests** (pattern of `asset-content-grid.columns.spec.ts`; `AssetContentService` spy; stub `NzModalService` via `overrideProvider`):
  - `where draft template is ayah_group and no rows should build group columns and show Add group` (Review Focus 1).
  - `where group template should not add sura and aya columns`.
  - `where editing a translated language should hide Add group and Move, and offer Delete only on orphaned rows` (Review Focus 4).
  - `where row is orphaned should make its text cells read-only`.
  - `where confirmGroup in add mode succeeds should flush pending edits, call addGroup and refresh the cache`.
  - `where addGroup fails with group_exists should keep the modal open with the translated error`.
  - `where moveGroup succeeds should call moveGroup with the row's unit_id and refresh`.
  - `where delete confirmed should call deleteGroup and refresh`.
  - `where commit fails with orphaned_groups should show the listed groups` (Review Focus 5).
  - `where template is ayah should render exactly the previous column ids` (regression: `['surah', 'sura', 'aya', 'reference_text', 'cell__text']`).
- [ ] **Step 2: Run** `npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/features/admin/components/asset-content-grid/**/*.spec.ts'` → new tests FAIL, existing pass.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the same command → all PASS.

---

### Task 5: Verify in the browser, docs, full checks

**Files:**
- Modify: `PROJECT_MAP.md`

**Interfaces:** Consumes everything above. Produces no code.

- [ ] **Step 1: Full checks** (Global Constraints list) → all pass; fix anything they report in files this plan touched.
- [ ] **Step 2: Browser check** (claude-in-chrome, user's Chrome; local backend from the backend worktree with its migration applied to both DBs): create a word-group tafsir; add a group 1:1:1 → 1:2:1 and watch the preview update while changing the end; edit its text; move it; delete another; download the CSV template (header only); commit; add a translated language and confirm it lists the source's groups with Add/Move hidden; publish the version and open the gallery asset page to confirm the file-structure panel shows the range header (`from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,text`) and the template badge reads "Word-group based". Record a GIF (`group_templates_editor.gif`).
- [ ] **Step 3: Performance check:** in the Network panel, typing in the picker fires at most one `quran-range` request per pause and cancels superseded ones; a group add triggers one POST plus the grid's block refetch only. Note the numbers in the summary.
- [ ] **Step 4: Update `PROJECT_MAP.md`** (`[SYSTEM_FLOW]`: tafsir group editing journey; `[ARCHITECTURE]`: `GroupRangeModalComponent`, group columns in the grid). `npx prettier --check PROJECT_MAP.md` passes.
