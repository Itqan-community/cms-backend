# Multi-Column Text Assets — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let translation and tafsir assets carry any number of named text columns, end to end in `itqan-cms-backend`. That covers storage, editor API, import/export, review, versioning, gallery preview, package catalog and Dependabot.

**Architecture:** A new `AssetColumn` model belongs to the asset. `AssetVersionEntry` and `AssetVersionChange` each gain a `column` FK, so every stored text is one *cell* `(unit, column)`. Every in-memory `{unit_id: text}` map becomes a `Snapshot = dict[CellKey, str]` keyed by `(unit_id, column_key)`. A committed version freezes its ordered column keys in `AssetVersion.column_keys`. An asset with no columns lazily gets one column keyed `text`, so every existing asset, file and test keeps working unchanged.

**Tech Stack:** Django 5.2, Python 3.13, django-ninja, simple-history (audit DB), modeltranslation, Postgres, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-multi-column-text-assets-design.md`

**Sibling plans (built after this one, against the API this plan produces):**
- `cms-frontend`: `docs/superpowers/plans/2026-10-21-multi-column-text-assets-frontend.md`, kept in this worktree next to this plan.
- `itqan-cli`: `docs/superpowers/plans/2026-10-21-multi-column-text-assets-cli.md`, same place.

## Global Constraints

- Follow `CLAUDE.md` / `.agents/rules/cms-backend.mdc`. **Do not commit.** The user commits by hand, so every "checkpoint" step only runs checks.
- Writes go through Service → Repository → ORM. Portal GET endpoints query models in the view.
- Every new `ItqanError` message uses `gettext_lazy`/`gettext` and gets an Arabic `msgstr`. Before you finish, run `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header` and then `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null`, which must report 0 untranslated.
- Tests use `apps.core.tests.base.BaseTestCase` (never raw `django.test.TestCase`) and AAA comments. Name them `test_<function>_where_<criteria>_should_<result>`, and put `self.authenticate_user` inside the test, not `setUp`. For 4xx responses, assert `error_name` as well as the status. Use `patch.object` with `<symbol>.__name__`. Run with `uv run pytest`, then `git checkout uv.lock` after any `uv run`.
- History tables live in the `audit` DB, so after migrating run `uv run manage.py migrate --database=audit` as well.
- Column key rules: `^[a-z][a-z0-9_]{0,63}$`, unique per asset. A key may not be any unit header (`sura`, `surah`, `aya`, `ayah`, `word`, `word_id`, `page`, `page_no`, `surah_name`, `ayah_text`).
- The default column key is exactly `text`. A single-column asset whose column is `text` must produce **byte-identical** CSVs to `staging`.
- New permission: `PORTAL_MANAGE_ASSET_COLUMNS = "portal_manage_asset_columns"`, label `_("Portal - Manage Asset Columns")`. Mutating columns needs it **and** `PORTAL_ACCESS_ALL_LANGUAGES`.
- Version bumps: adding a column is minor. Reordering keys that were in the predecessor version requires `bump="major"`; a minor bump in that case fails with `major_bump_required`.
- Preview: at most `3` rows, with no access grant required.
- The manifest comment marker is exactly `# itqan:columns`. The format is defined in Task 10 and is shared byte-for-byte with `itqan-cli`.
- Never regress the query counts of the editor entries page, CSV generation, catalog or asset detail for single-column assets. Measure against `staging` (Task 11).

## Review Focus

1. **Existing single-column assets after the migration.** Editor, review, export, package download and Dependabot must behave exactly as before. That means the CSV header stays `text` and the bytes match. Pinned in Tasks 1 and 3.
2. **A translation of a multi-column asset whose source gained a column after the translation's last commit.** The editor shows the new column (empty), the commit carries the full key list, and nothing crashes on a missing source cell. Pinned in Task 4.
3. **Restoring or exporting a pruned (delta-only) version committed before a later column was added.** The output uses *that* version's `column_keys`, not today's. Pinned in Task 3.
4. **Deleting or re-keying a column that only an old, superseded committed version contains.** This must still be refused, because the key is in that version's `column_keys`. Pinned in Task 2.
5. **Dependabot bumping an entry that has a hand-written comment directly above it.** Only lines starting with `# itqan:columns` are replaced, and the user's comment survives. Pinned in Task 10.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `apps/content/models.py` (modify) | `AssetColumn`; `column` FK on `AssetVersionEntry` / `AssetVersionChange`; `AssetVersion.column_keys`; `Asset.text_columns()`; `AssetVersion.resolved_column_keys` |
| `apps/content/translation.py` (modify) | register `AssetColumn.label` for modeltranslation |
| `apps/content/migrations/0008_…`–`0010_…` (create) | schema, batched backfill, NOT NULL + new unique constraints |
| `apps/content/columns.py` (create) | `CellKey`, `Snapshot`, `UNIT_HEADERS`, `validate_column_key()`, `csv_header()` — pure helpers shared by repo/import/catalog |
| `apps/content/repositories/asset_columns.py` (create) | ORM access for columns |
| `apps/content/services/asset_columns.py` (create) | column CRUD rules, `version_structure()` |
| `apps/content/api/portal/asset_columns.py` (create) | portal column endpoints |
| `apps/content/repositories/asset_content.py` (modify) | snapshots per cell, CSV per column, commit freezes keys |
| `apps/content/services/asset_content.py` (modify) | cells in entries page/patch/pending, major-bump rule |
| `apps/content/services/asset_templates.py` (modify) | per-column text filters |
| `apps/content/services/asset_content_import.py` (modify) | multi-column parse |
| `apps/content/api/portal/asset_content.py` (modify) | `cells`, patch `column`, dynamic filters, `requires_major` |
| `apps/content/repositories/asset_review.py`, `apps/content/api/portal/asset_review.py` (modify) | review per cell |
| `apps/content/api/internal/asset_file_structure.py` (create) | gallery "File structure" endpoint |
| `apps/package_manager/api/public/packages.py`, `services/package_registry.py` (modify) | `structure` on catalog/resolve |
| `apps/package_manager/services/columns_comment.py` (create) | render the `# itqan:columns` block |
| `apps/dependabot/services/manifest_update.py`, `pr_updater.py` (modify) | refresh the block on bump |
| `apps/core/permissions.py` (modify) | new permission |
| `docs/ARCHITECTURE.md`, `docs/ASSET_MANIFEST.md`, `docs-website/docs/…packages…` (modify) | docs |

---

### Task 1: Column storage, lazy default column, backfill

**Files:**
- Modify: `apps/content/models.py`, `apps/content/translation.py`
- Create: `apps/content/columns.py`
- Create: `apps/content/migrations/0008_asset_columns.py`, `0009_backfill_asset_columns.py`, `0010_asset_columns_required.py`
- Test: `apps/content/tests/models/test_asset_columns.py`

**Interfaces:**
- Produces:
  - `class AssetColumn(BaseModel)`: `asset` FK(`Asset`, CASCADE, `related_name="columns"`), `key: CharField(max_length=64)`, `label: CharField(max_length=255, blank=True, default="")` (modeltranslation → `label_en`, `label_ar`), `order: PositiveIntegerField(default=0)`. `HistoricalRecords` exactly like `AssetLanguage`. Meta: `UniqueConstraint(["asset","key"], name="unique_column_key_per_asset")`, `ordering = ["order", "id"]`.
  - `AssetVersionEntry.column` FK(`AssetColumn`, CASCADE, `related_name="entries"`). Uniques become `(version, <unit>, column)` with the same constraint names plus suffix `_column`, e.g. `unique_entry_per_version_ayah_column`.
  - `AssetVersionChange.column` FK(`AssetColumn`, PROTECT, `related_name="changes"`).
  - `AssetVersion.column_keys: JSONField(default=list, blank=True)` holds the ordered keys frozen at commit, and is empty on drafts.
  - `Asset.text_columns() -> list[AssetColumn]`: ordered columns. For a translation/tafsir with none, it creates `AssetColumn(key="text", order=0)` via `get_or_create` (lazy, like `get_or_create_source_language`). Other categories get `[]`.
  - `AssetVersion.resolved_column_keys -> list[str]` (property): `column_keys` if non-empty, else `[c.key for c in asset.text_columns()]`.
  - `AssetVersionEntry.save()` / `AssetVersionChange.save()`: when `column_id is None`, set `column = self.version.asset.text_columns()[0]`. This keeps every existing `objects.create` / `baker.make` caller valid. `bulk_create` callers must set `column` explicitly (Tasks 3–5 do).
  - `apps/content/columns.py`:
    - `CellKey = tuple[int, str]` (unit_id, column_key); `Snapshot = dict[CellKey, str]`.
    - `UNIT_HEADERS: frozenset[str]`, the reserved names listed in Global Constraints.
    - `validate_column_key(key: str) -> None` raises `ItqanError("column_key_invalid", 400)`.
    - `csv_header(template: AssetTemplateChoice, column_keys: list[str], *, verbose: bool = False) -> list[str]` returns the unit headers exactly as `_units_to_csv_bytes` writes them today (`["sura"]`, `["surah","ayah"]`, verbose `["surah","ayah","surah_name","ayah_text"]`, `["word_id","sura","aya","word"]`, `["page"]`) + `column_keys`.

- [ ] **Step 1: Write failing model tests** in `test_asset_columns.py` (`QuranDataMixin, BaseTestCase`):
  - `test_text_columns_where_tafsir_has_none_should_create_text_column`: `[c.key for c in asset.text_columns()] == ["text"]`, and calling it twice leaves `AssetColumn.objects.filter(asset=asset).count() == 1`.
  - `test_text_columns_where_mushaf_should_return_empty`: `== []`, with no row created.
  - `test_entry_save_where_column_missing_should_default_to_first_column`: `AssetVersionEntry.objects.create(version=v, ayah=a, text="x").column.key == "text"`.
  - `test_resolved_column_keys_where_version_has_frozen_keys_should_return_them`: `column_keys=["question","answer"]` → the same list, even after the asset gains `"extra"`.
  - `test_entry_unique_where_same_unit_two_columns_should_allow_both`, and `..._same_unit_same_column_should_raise_integrity_error`.
  - `test_csv_header_where_ayah_two_columns_should_append_keys`: `csv_header(AYAH, ["question","answer"]) == ["surah","ayah","question","answer"]`.
  - `test_validate_column_key_where_reserved_or_malformed_should_raise`: for `"sura"`, `"Question"` and `"1a"`, assert `error_name == "column_key_invalid"`.
- [ ] **Step 2:** `uv run pytest apps/content/tests/models/test_asset_columns.py -q` should FAIL (import errors).
- [ ] **Step 3: Implement models + `columns.py` + translation registration.**
- [ ] **Step 4: Migrations.**
  - `0008`: create `AssetColumn`, add a **nullable** `column` FK to entry and change, add `column_keys`, and keep the old unique constraints.
  - `0009` (`atomic = False`, `RunPython` with a no-op reverse):
    1. Create `AssetColumn(key="text", order=0)` for every asset with `category in (translation, tafsir)` that has none.
    2. Set `column_id` on entries and on changes in batches of 50 000 ids, using raw SQL `UPDATE … FROM content_assetversion v JOIN content_assetcolumn c ON c.asset_id = v.asset_id AND c.key='text' WHERE … id BETWEEN %s AND %s AND column_id IS NULL`.
    3. Set `column_keys=["text"]` on every committed (`state=published`) version of those assets.
  - `0010`: make both FKs non-null, drop the four old entry uniques and add the four `_column` ones.
  - Then run `uv run makemigrations` (no further changes expected), `uv run manage.py migrate`, and `uv run manage.py migrate --database=audit`. Check the generated historical-model migration: historical `column` must be nullable (no default prompt). If makemigrations asks, make it nullable in the history model.
- [ ] **Step 5:** Run the model tests, then the whole `apps/content` suite: `uv run pytest apps/content -q -x`. Everything existing must PASS unchanged; that is proof the lazy default works.
- [ ] **Step 6: Docs.** Update `docs/ARCHITECTURE.md` to cover the model, the fields and the mermaid ER diagram (`AssetColumn`, entry/change → column).
- [ ] **Step 7: Checkpoint.** Run `git status`, then `git checkout uv.lock`. Don't commit.

---

### Task 2: Permission and column management API

**Files:**
- Modify: `apps/core/permissions.py`
- Create: `apps/content/repositories/asset_columns.py`, `apps/content/services/asset_columns.py`, `apps/content/api/portal/asset_columns.py`
- Modify: the portal router registration (where `asset_content.router` is mounted; find it with `grep -rn "asset_content import router\|asset_content.router" apps`)
- Test: `apps/content/tests/portal/test_asset_columns_api.py`, `apps/content/tests/services/test_asset_columns_service.py`

**Interfaces:**
- Consumes: Task 1 models, `validate_column_key`.
- Produces:
  - `PermissionChoice.PORTAL_MANAGE_ASSET_COLUMNS`, plus implication `{PORTAL_READ_TAFSIR, PORTAL_READ_TRANSLATION}`.
  - `AssetColumnService`:
    - `list_columns(asset) -> list[AssetColumn]`
    - `create_column(asset, *, key: str, label_en: str = "", label_ar: str = "") -> AssetColumn`, appended last.
    - `update_column(column, *, key: str | None = None, label_en: str | None = None, label_ar: str | None = None) -> AssetColumn`
    - `reorder_columns(asset, keys: list[str]) -> list[AssetColumn]`
    - `delete_column(column) -> None`
    - `is_committed(column) -> bool`: true when any `AssetVersion(asset=column.asset, state=PUBLISHED, column_keys__contains=[column.key])` exists, **or** any `AssetVersionChange(column=column)` exists.
  - Errors:
    - `column_key_invalid` 400, `column_key_taken` 400.
    - `column_committed` 400: re-key or delete of a committed column. Message: `_("This column is part of a committed version, so it can't be renamed or deleted.")`
    - `column_last` 400: deleting the only column.
    - `column_order_mismatch` 400: `keys` isn't exactly the asset's current key set.
    - `column_not_found` 404.
  - Endpoints, all under `content/{category}/{slug}/columns/`, reusing `_resolve` / `_CATEGORY_CONFIG` from `asset_content.py` (import them, don't copy):
    - `GET ""` → `list[AssetColumnOut]`, `access="read"`.
    - `POST ""` (`AssetColumnIn{key, label_en="", label_ar=""}`) → 201 `AssetColumnOut`.
    - `PATCH "{key}/"` (`AssetColumnPatchIn{key?, label_en?, label_ar?}`).
    - `PUT "order/"` (`{keys: list[str]}`).
    - `DELETE "{key}/"` → 204.
  - Mutations call `_require_manage_columns(request)`: `check_permission(user, PORTAL_MANAGE_ASSET_COLUMNS, raise_exception=True)` and `check_permission(user, PORTAL_ACCESS_ALL_LANGUAGES, raise_exception=True)`.
  - `AssetColumnOut{key, label_en, label_ar, order, committed: bool}`.

- [ ] **Step 1: Failing tests.**
  - Service tests:
    - Create appends with `order == 1` after `text`.
    - A duplicate key gives `column_key_taken`.
    - Re-keying an uncommitted column works.
    - Re-keying or deleting when **an old superseded committed version** has the key in `column_keys` gives `column_committed` (Review Focus 4).
    - Deleting the only column gives `column_last`.
    - Deleting an uncommitted column cascades its draft entries.
    - Reorder with a wrong key set gives `column_order_mismatch`.
  - API tests:
    - Without `PORTAL_MANAGE_ASSET_COLUMNS`, POST returns 403.
    - With it but without all-languages access, POST returns 403.
    - With both, POST returns 201 with `key`, labels and `committed=False`.
    - GET works with read permission only.
    - `committed` reflects reality.
- [ ] **Step 2:** Run them; they should FAIL.
- [ ] **Step 3:** Implement the repo, service and router. Lock the asset row (`select_for_update`) in create, reorder and delete so concurrent edits serialize.
- [ ] **Step 4:** Tests PASS. Then run makemessages, translate the new strings to Arabic, and run `msgfmt --check`.
- [ ] **Step 5: Docs.** In `docs/ARCHITECTURE.md`, cover the permission and who may manage columns.
- [ ] **Step 6: Checkpoint** (no commit).

---

### Task 3: Cell snapshots, history, and CSV per column

**Files:**
- Modify: `apps/content/repositories/asset_content.py`
- Test: `apps/content/tests/services/test_asset_content_columns.py`, and extend `test_asset_content_export_templates.py`

**Interfaces:**
- Consumes: `Snapshot`, `CellKey`, `csv_header`, `AssetVersion.resolved_column_keys`, `Asset.text_columns()`.
- Produces (signature changes; update every caller found by `grep -rn "<name>(" apps`):
  - `_entries_map(version) -> Snapshot`: read via `values_list(<unit>, "column__key", "text")`, one query.
  - `reconstruct_entries(version) -> Snapshot`: changes contribute `(change.unit_id, change.column.key)`. Add `"changes__column"` / `"entries__column"` to the prefetch.
  - `_record_changes(new_version, previous_head) -> dict[str, int]` diffs per cell. Rows set `column=` from a `{key: AssetColumn}` map of the asset.
  - `diff_maps(spec, old: Snapshot, new: Snapshot) -> list[dict]`: every dict gains `"column": key`, ordered by `(unit_id, column order)`.
  - `version_diff(version)`: stored rows add `"column": c.column.key` (add `"column"` to `select_related`).
  - `_units_to_csv_bytes(spec, cells: Snapshot, column_keys: list[str], *, verbose, page_count) -> bytes`: header from `csv_header`, one cell per key per row.
  - `entries_to_csv_bytes(version, spec, *, verbose=False)` / `snapshot_to_csv_bytes(snapshot, spec, *, asset, column_keys: list[str], verbose=False)` / `blank_template_csv_bytes(spec, *, page_count, column_keys: list[str] = ["text"])`. Callers pass `version.resolved_column_keys`. This includes `store_generated_package_file` in `apps/package_manager/repositories/package_registry.py`.
  - `publish_draft(draft)`: sets `draft.column_keys = [c.key for c in draft.asset.text_columns()]` and adds `"column_keys"` to `update_fields`, **before** building the CSV.
  - `restore_version(version, *, name, created_by_id)`: the new version's `column_keys` are the asset's current keys, and cells come from the snapshot (all their keys still exist, because committed columns can't be deleted).
  - `ensure_entries`, `_snapshot_from_file`, `create_draft_seeded_from`, `ensure_mushaf_coverage`, `replace_entries_from_parsed`, `upsert_entries` write the `column` explicitly on every `AssetVersionEntry(...)`.
    - Mushaf overlay: one empty row per *(mushaf ayah, asset column)*.
    - Seeding copies `column_id`.
    - `upsert_entries` rows become `{"unit_id", "column", "text"}`, where `column` defaults to the first key.
    - Existing rows are looked up by `(unit_id, column_key)`.

- [ ] **Step 1: Failing tests:**
  - `test_entries_to_csv_bytes_where_single_text_column_should_match_staging_bytes`, for each template (surah, ayah lean, ayah verbose, word, page). Build the expected bytes by hand with today's headers (`sura,text` / `surah,ayah,text` / …) and assert `==`.
  - `test_entries_to_csv_bytes_where_two_columns_should_write_both`: header `surah,ayah,question,answer`, and the row for 1:1 is `1,1,Q,A`.
  - `test_publish_draft_where_two_columns_should_freeze_column_keys`.
  - `test_record_changes_where_one_cell_modified_should_record_one_change_with_column`.
  - `test_reconstruct_entries_where_pruned_version_should_rebuild_cells`. Commit v1 with Q and A, commit v2 changing only A (v1 is pruned), then `reconstruct_entries(v1) == {(ayah, "question"): "Q", (ayah, "answer"): "A"}`.
  - `test_snapshot_to_csv_bytes_where_version_predates_new_column_should_use_its_own_keys` (Review Focus 3). Commit v1 with `[question, answer]`, add `extra`, commit v2. Exporting v1 has no `extra` header; exporting v2 has it.
  - `test_restore_version_where_old_version_lacks_new_column_should_use_current_keys_with_blank`.
  - `test_create_draft_seeded_from_where_translation_of_two_column_asset_should_seed_row_per_ayah_and_column`.
- [ ] **Step 2:** Run; FAIL.
- [ ] **Step 3:** Implement the signatures above.
- [ ] **Step 4:** New tests PASS, and `uv run pytest apps/content apps/package_manager -q` is all green.
- [ ] **Step 5: Checkpoint.**

---

### Task 4: Editor API — cells, patch, filters, pending diff, export, templates

**Files:**
- Modify: `apps/content/services/asset_templates.py`, `apps/content/services/asset_content.py`, `apps/content/api/portal/asset_content.py`
- Test: `apps/content/tests/portal/test_asset_content_columns.py`

**Interfaces:**
- Consumes: Task 3 repository signatures.
- Produces:
  - `EntryFilters`: replace `text` / `source_text` with `cells: Mapping[str, ColumnFilter]` and `source_cells: Mapping[str, ColumnFilter]` (default empty). `active` accounts for them. `UnitSpec._entry_text(version, column_key)` adds `column__key=column_key` to the subquery, and `_filter_pages` reads per key.
  - `EntriesFilterModelIn`: switch to `extra="allow"`. Known keys are as today. Accept `cell__<key>` and `source__<key>`. `text` maps to `cell__<first key>` and `source_text` to `source__<first key>`. Any other extra key, or an unknown column key, raises `ItqanError("unknown_filter_column", 400)`. `to_filters(column_keys: list[str]) -> EntryFilters`.
  - `EntryOut` adds `cells: dict[str, str]` (every asset column key, `""` when empty) and `source_cells: dict[str, str] | None`. It **keeps** `text` / `source_text` as the first column, so older frontends keep working. `changed` is true when any cell differs.
  - `EntryPatchRow{unit_id: int, column: str | None = None, text: str = ""}`. `None` means the first column, and an unknown column gives `unknown_column` 400.
  - `get_entries_page(...)` returns those rows. `source_cells` uses the source version's cells for the **asset's current keys**, so missing source cells read `""`, never `KeyError` (Review Focus 2).
  - `get_pending_changes` / `version_diff` items include `column`; `ChangeOut` gains `column: str`.
  - `DraftVersionOut` gains `column_keys: list[str]` (the live asset keys for drafts, frozen for committed versions), plus `requires_major` (Task 7 fills it in; here it's `False`).
  - `export_version` uses `resolved_column_keys`.
  - `download_csv_template` (pre-create) stays single-column `text`.
  - `download_asset_csv_template` passes the asset's keys.

- [ ] **Step 1: Failing tests** with a two-column ayah tafsir (`question`, `answer`):
  - GET entries returns `cells == {"question": "", "answer": ""}` for empty units, and `text` equals the `question` value.
  - PATCH `{"rows":[{"unit_id":a,"column":"answer","text":"A"}]}` returns 200, and the entry is stored under `answer`.
  - PATCH with `"column":"nope"` returns 400 with `error_name == "unknown_column"`.
  - Filter `{"cell__answer":{"filterType":"text","type":"contains","filter":"A"}}` returns only matching rows. `{"cell__nope":…}` returns 400 `unknown_filter_column`.
  - A translation rendition (`en`) of the asset, where the source later gained `extra`: GET entries returns `source_cells["extra"] == ""` and `cells["extra"] == ""`, with status 200 (Review Focus 2).
  - Pending diff items include `"column"`.
  - Asset CSV template has header `surah,ayah,surah_name,ayah_text,question,answer`.
  - Existing tests in `test_asset_content*.py` still pass. That's the compatibility check on `text`/`source_text`.
- [ ] **Step 2:** Run; FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS, plus `uv run pytest apps/content -q`. Makemessages and Arabic translations for `unknown_column` / `unknown_filter_column`.
- [ ] **Step 5: Checkpoint.**

---

### Task 5: Multi-column CSV import

**Files:**
- Modify: `apps/content/services/asset_content_import.py`, the callers in `apps/content/services/asset_content.py` and `apps/content/repositories/asset_content.py`
- Test: `apps/content/tests/services/test_asset_content_import_columns.py`

**Interfaces:**
- Produces:
  - `ParsedEntry(unit_id: int, cells: dict[str, str])`, replacing `text`.
  - `parse_content_file(raw, spec, asset, *, column_keys: list[str], strict=False) -> list[ParsedEntry]`. With one key, that key's accepted headers are `_TEXT_HEADERS | {key}` (today's behaviour). With several keys, each key accepts only its exact name.
  - Header detection: unit headers plus at least one accepted text header. Every key must be present, or it raises `AssetContentMissingColumnsError(missing: list[str])`, a subclass of `AssetContentParseError`.
  - Blank cells are skipped, and a row with every cell blank is skipped. A duplicate unit with different cells is a `DUPLICATE` problem.
  - `import_uploaded_file_into_entries` / `import_file_into_version` map `AssetContentMissingColumnsError` to `ItqanError("content_file_missing_columns", 400, extra={"missing": [...]})`. The message is `_("The file is missing these columns: {columns}.")`, and both endpoints' `NinjaErrorResponse` unions declare it.
  - Callers pass `column_keys=asset text keys` (`_snapshot_from_file` passes `version.resolved_column_keys`).

- [ ] **Step 1: Failing tests:**
  - A single-column file with header `id,sura,aya,translation` still parses (`cells == {"text": ...}`).
  - A two-column asset with header `surah,ayah,question,answer` parses both.
  - A two-column asset whose header has only `answer` raises `AssetContentMissingColumnsError` with `missing == ["question"]`. The API upload returns 400 `content_file_missing_columns`.
  - In a two-column asset, the alias `translation` isn't accepted for `question`.
  - Strict mode flags a duplicate with different cells.
- [ ] **Step 2–4:** Run (FAIL), implement, run (PASS), plus `uv run pytest apps/content -q`, then makemessages and Arabic.
- [ ] **Step 5: Checkpoint.**

---

### Task 6: Review per cell

**Files:**
- Modify: `apps/content/repositories/asset_review.py`, `apps/content/api/portal/asset_review.py`
- Test: `apps/content/tests/portal/test_asset_review_columns.py`

**Interfaces:**
- Produces:
  - The pending key becomes `(unit_key, column_id)` in `pending_cells_by_version`.
  - `changes_for` partitions the window by `[unit_key, F("column_id")]`, and `earlier_approved_text` filters `column_id=OuterRef("column_id")`.
  - `select_related("column")`.
  - `ReviewChangeOut` gains `column: str` (key), `column_label_en: str` and `column_label_ar: str`.
- [ ] **Step 1: Failing tests.**
  - Committing a Q change and an A change on the same ayah gives 2 pending.
  - Approving only Q leaves 1 pending, and `set_published_version` returns 400 `version_not_approved`.
  - `as_of` lists both cells.
  - `baseline_text` of A ignores Q's approved text.
- [ ] **Step 2–4:** FAIL → implement → PASS, plus `uv run pytest apps/content -q`.
- [ ] **Step 5: Checkpoint.**

---

### Task 7: Major bump on column reorder

**Files:**
- Modify: `apps/content/services/asset_content.py`, `apps/content/api/portal/asset_content.py`
- Test: `apps/content/tests/portal/test_version_numbering_columns.py`

**Interfaces:**
- Produces:
  - `requires_major_bump(previous_keys: list[str], new_keys: list[str]) -> bool` in `apps/content/columns.py`: True when the keys of `previous_keys` don't appear in `new_keys` in the same relative order. Appending or inserting new keys alone is False.
  - `AssetContentService.publish_draft` and `restore_version`: when the language has a previous committed version, `requires_major_bump(previous.resolved_column_keys, current asset keys)` is True, and `bump == "minor"`, raise `ItqanError("major_bump_required", 400)` with message `_("Columns were reordered since the last version. Reordering changes the file layout, so this must be a major version.")`. Declare it in both endpoints' responses.
  - `DraftVersionOut.requires_major` is computed the same way for drafts, and is False otherwise.
- [ ] **Step 1: Failing tests.**
  - Pure function: `(["a","b"],["a","b","c"]) → False`, `(["a","b"],["c","a","b"]) → False`, `(["a","b"],["b","a"]) → True`.
  - Publish with `bump="minor"` after a reorder returns 400 `major_bump_required`, and `bump="major"` returns 200 with name `2.0`.
  - Adding a column, then minor, gives `1.1`.
  - The draft GET shows `requires_major: true` after a reorder.
- [ ] **Step 2–4:** FAIL → implement → PASS, then makemessages and Arabic.
- [ ] **Step 5: Checkpoint.**

---

### Task 8: Gallery "File structure" endpoint

**Files:**
- Modify: `apps/content/services/asset_columns.py`
- Create: `apps/content/api/internal/asset_file_structure.py`, and register it next to `assets_detail.router`
- Test: `apps/content/tests/internal/test_asset_file_structure.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) VersionStructure(template: str, header: list[str], columns: list[ColumnInfo])` and `ColumnInfo(key, label_en, label_ar)`, both in `apps/content/services/asset_columns.py`.
  - `version_structure(version: AssetVersion) -> VersionStructure`: keys from `resolved_column_keys`, labels from the asset's current `AssetColumn`s, and header from `csv_header(template, keys)` (lean).
  - `GET /cms-api/assets/{id}/file-structure/?language=<code>`, `auth=None`. The response is `AssetFileStructureOut{format: "csv", template, header, columns: list[ColumnInfoOut], rows: list[list[str]]}`.
  - The asset lookup is the same as in `detail_assets`: `request.publisher_q("publisher")`, `restricted_for_tenant=False`.
  - Only translation/tafsir with `status=READY`. The language must be READY with a `published_version`; otherwise 404 `file_structure_unavailable`. `language` defaults to the source rendition.
  - `rows`: the first `3` units of the published version (by entry `order`, then unit) that have any non-empty cell, rendered like CSV rows (unit header values + cells). A published version without entries (legacy file-only) gives `rows=[]`.
  - Query budget: at most 6 queries (assert with `assertNumQueries`).
- [ ] **Step 1: Failing tests.**
  - Two-column published asset: header `["surah","ayah","question","answer"]`, at most 3 rows, `rows[0] == ["1","1","Q","A"]`.
  - Anonymous request returns 200 (no access grant needed).
  - DRAFT language returns 404 `file_structure_unavailable`.
  - Single-column asset: header `["surah","ayah","text"]`.
  - Number of queries ≤ 6.
- [ ] **Step 2–4:** FAIL → implement → PASS, then makemessages and Arabic.
- [ ] **Step 5: Checkpoint.**

---

### Task 9: Package catalog and resolve expose `structure`

**Files:**
- Modify: `apps/package_manager/services/package_registry.py`, `apps/package_manager/api/public/packages.py`
- Modify: `docs-website/docs/` (find the packages page with `grep -rln "packages/" docs-website/docs`)
- Test: `apps/package_manager/tests/test_package_registry_structure.py`

**Interfaces:**
- Consumes: `version_structure()`.
- Produces:
  - `PackageStructureOut{template: str, header: list[str], columns: list[PackageColumnOut{key, label_en, label_ar}]}`.
  - `PackageLanguageOut.structure: PackageStructureOut | None` comes from the **latest** installable version. That means `CatalogLanguage` gains `latest: AssetVersion`, and `catalog_languages` keeps it.
  - `PackageVersionOut.structure: PackageStructureOut | None` comes from the resolved version.
  - Non-text categories get `None`.
  - Prefetch `columns` on the catalog queryset (`list_installable_assets`) so the catalog page doesn't run N+1 queries.
- [ ] **Step 1: Failing tests.**
  - The catalog entry for a two-column tafsir has `languages[0].structure.header == ["surah","ayah","question","answer"]`, with labels.
  - `POST` manifest resolve returns `results[0].structure`.
  - A mushaf has `structure is None`.
  - The catalog query count for 5 assets equals the count for 1 asset (constant), measured with `CaptureQueriesContext`.
- [ ] **Step 2–4:** FAIL → implement → PASS. Document both fields in `docs-website`.
- [ ] **Step 5: Checkpoint.**

---

### Task 10: Manifest comment block and Dependabot refresh

**Files:**
- Create: `apps/package_manager/services/columns_comment.py`
- Modify: `apps/dependabot/services/manifest_update.py`, `apps/dependabot/services/pr_updater.py`, `docs/ASSET_MANIFEST.md`, `docs/DEPENDABOT.md`
- Test: `apps/package_manager/tests/test_columns_comment.py`, extend `apps/dependabot/tests/test_manifest_update.py`, `test_pr_updater.py`

**The block format (normative; write it verbatim into `docs/ASSET_MANIFEST.md` §2 as "Column comment block"):**

```text
<indent># itqan:columns CSV, one row per <template>: <header joined by ", ">
<indent># itqan:columns   <key>: <label_en> / <label_ar>      (one line per column with a label)
```

- `<indent>` is the entry key's indentation, and the block sits on the lines directly above the entry key.
- `<template>` is `surah` | `ayah` | `word` | `page`.
- Label lines use `label_en / label_ar`, or just whichever one exists. A column with no labels gets no line.
- The block is written only when the version has **more than one** column. Otherwise any existing block is removed.
- Replacement removes exactly the consecutive lines directly above the key that start (after indentation) with `# itqan:columns`, and leaves every other comment alone.

**Interfaces:**
- Produces:
  - `render_columns_comment(structure: VersionStructure, indent: str) -> list[str]` returns lines without a trailing newline, and `[]` when single-column.
  - `update_manifest_content(raw_manifest, slug, new_constraint, *, columns_comment: Callable[[str], list[str]] | None = None) -> bytes`. When `columns_comment` is given, it is called with the entry key's detected indentation, and the block above the entry is replaced with the lines it returns. `[]` means removal. `None` leaves comments untouched (today's callers).
  - The out-of-range branch of `pr_updater` passes `columns_comment=lambda indent: render_columns_comment(version_structure(asset_version), indent)`.
  - The in-range branch (lockfile only today) also fetches the manifest and runs `update_manifest_content` with the **unchanged** constraint and the same `columns_comment`. If the bytes differ, meaning a minor version added a column, it adds `MANIFEST_PATH` to `files`. Otherwise the PR stays lockfile-only. If the manifest can't be read, it falls back to lockfile-only and doesn't skip.
- [ ] **Step 1: Failing tests.**
  - Render for the Q&A example equals the exact lines in the spec example.
  - Single-column renders `[]`.
  - The update replaces an old block, keeps a user comment line directly above the block (Review Focus 5), inserts a block when none exists, removes it when given `[]`, and leaves the bytes byte-identical when `None`.
  - In the pr_updater out-of-range path, the manifest contains the block.
  - An in-range bump to a version that added a column includes `MANIFEST_PATH` with the refreshed block. An in-range bump with no column change stays lockfile-only.
- [ ] **Step 2–4:** FAIL → implement → PASS. Update the docs.
- [ ] **Step 5: Checkpoint.**

---

### Task 11: Performance, localization and docs gate

**Files:** none new. This task measures and fixes.

- [ ] **Step 1:** Query counts versus `staging` for a single-column ayah tafsir:
  - entries page (`page_size=100`), with and without a text filter
  - PATCH of 1 row
  - `entries_to_csv_bytes`
  - `GET /packages/` with 5 assets
  - `GET cms-api/assets/{id}/`

  Write a throwaway test using `CaptureQueriesContext`. Run it on this branch and on a `staging` checkout (`git worktree add --detach ../tmp-staging origin/staging`), then fix any increase. Report the numbers in the final summary.
- [ ] **Step 2:** Run the full suite: `uv run pytest -q`. Then `git checkout uv.lock`.
- [ ] **Step 3:** Run makemessages, then `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null` (0 untranslated, no fuzzy entries), then `compilemessages`.
- [ ] **Step 4:** Run pre-commit on each changed file separately: `for f in $(git diff --name-only staging...; git ls-files -o --exclude-standard); do pre-commit run --files "$f"; done`.
- [ ] **Step 5:** Re-read `docs/ARCHITECTURE.md`, `ASSET_MANIFEST.md`, `DEPENDABOT.md` and `docs-website` for stale statements about "one text per ayah", and fix them.
- [ ] **Step 6:** Write the final summary: surfaces checked (gallery detail, file-structure, package catalog/resolve/download, Dependabot, review, editor), the query numbers, the localization count, and the docs updated.
