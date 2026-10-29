# Ayah-Group / Word-Group Templates — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tafsir assets can use two new templates, `ayah_group` and `word_group`, whose rows each cover a publisher-defined range of ayahs or words, end to end: storage, import, export, editing, history, review and translation languages.

**Architecture:** A group row stores its range in four new nullable FK columns (`from_ayah`/`to_ayah`, `from_word`/`to_word`) on `AssetVersionEntry` and `AssetVersionChange`. Everywhere the pipeline keys a cell by `unit_id: int`, a group is keyed by an **encoded int** `from_id * GROUP_KEY_BASE + to_id` (`GROUP_KEY_BASE = 1_000_000`, above every `Ayah.id` and `Word.id`), so `Snapshot`, diffing, reconstruction, `EntryOut.unit_id`, `ChangeOut.unit_id` and `EntryPatchRow.unit_id` keep their `int` type, and sorting by key is sorting by (from, to). `UnitSpec` (in `asset_templates.py`) stays the single place that branches on template; a new pure module `apps/content/unit_keys.py` owns the encoding and the template-agnostic SQL/Q helpers.

**Tech Stack:** Django 5.2, Django Ninja, PostgreSQL, pytest, model_bakery, simple_history.

**Spec:** `docs/superpowers/specs/2026-10-25-group-templates-design.md` (read it first; this plan argues from it).

## Global Constraints

- Work only in this worktree: `/Users/Apple/Documents/projects/cms/itqan-cms-backend-group-templates` (branch `feat/group-templates`).
- **Never commit** (backend rule: the user handles all commits). Leave every change in the working tree. Reviewers diff the working tree against `origin/staging`.
- Environment: run `uv sync --group dev` once in the worktree; after **every** `uv run …` run `git checkout -q uv.lock` (local uv rewrites it).
- Tests: `uv run pytest <path> --create-db` the first time, then without `--create-db`. Every test class extends `apps.core.tests.base.BaseTestCase` (never raw `django.test.TestCase`).
- Test names `test_<function>_where_<criteria>_should_<result>`; explicit `# Arrange` / `# Act` / `# Assert` comments; `self.authenticate_user(...)` inside the test, never in `setUp`; assert `error_name` on every 4xx; patch with `patch.object(<module>, <symbol>.__name__)`.
- Errors: `ItqanError(error_name=..., message=_("..."), status_code=...)` with `gettext_lazy`/`gettext` messages; declare each new `error_name` in the endpoint's `NinjaErrorResponse[Literal[...]]`.
- Migrations: `DB_NAME=nonexistent_mm AUDIT_DB_NAME=nonexistent_mm uv run manage.py makemigrations content` (local DB history drifts). New migration is `apps/content/migrations/0011_*.py`. History models live in the `audit` DB: tell the user to run `migrate --database=audit` too.
- Template values exactly: `ayah_group` → label `_("Ayah-group based")`; `word_group` → `_("Word-group based")` (`Asset.template` is `max_length=10`; both fit).
- Group templates are **tafsir-only**. Single-unit templates keep their current behaviour byte for byte (existing tests must pass untouched).
- Every function you add is type hinted (endpoints excepted). Python 3.13.
- Localization gate before reporting done: `extendedmakemessages` (Actions in CLAUDE.md) → fill every Arabic `msgstr` in `locale/ar/LC_MESSAGES/django.po` → `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null` reports 0 untranslated, no stray `fuzzy` → `compilemessages` succeeds.
- Pre-commit hooks: run per file (`for f in $(git diff --name-only; git ls-files -o --exclude-standard); do uv run --frozen pre-commit run --files "$f"; done`) — multi-file runs silently skip.

## Review Focus

1. **Overlapping groups that start at the same ayah** (2:1→2:5 and 2:1→2:1): both stored, listed, exported, diffed and reviewed as separate rows. → test in Task 1 (constraint) and Task 3 (`_record_changes`).
2. **A word group crossing an ayah or surah boundary** (1:3:1 → 2:1:2): valid on import, in the grid, in the preview endpoint, with reference text spanning both ayahs. → tests in Task 2, Task 6 and Task 7.
3. **A translated language after the source moved a group**: the old range shows as an orphaned row, still deletable, and commit is refused while it holds text. → test in Task 7.
4. **Re-importing an exported file** (verbose export carries `reference_text`): imports back to identical cells. → test in Task 4.
5. **Clearing a group's last text in a draft and committing**: the group disappears and the change is recorded as `removed`, while the draft grid still shows the row until commit. → test in Task 3.

---

### Task 1: Group key encoding, template choices and range columns

**Files:**
- Create: `apps/content/unit_keys.py`
- Modify: `apps/content/models.py` (`AssetTemplateChoice` ~line 77; `AssetVersionEntry` ~line 808; `AssetVersionChange` ~line 940)
- Create: `apps/content/migrations/0011_group_templates.py` (generated)
- Create: `apps/content/tests/group_quran_data.py`
- Test: `apps/content/tests/models/test_group_units.py`

**Interfaces:**
- Produces (`apps/content/unit_keys.py`, no model imports):
  - `GROUP_KEY_BASE: int = 1_000_000`
  - `encode_group_key(from_id: int, to_id: int) -> int`
  - `decode_group_key(key: int) -> tuple[int, int]` (`divmod(key, GROUP_KEY_BASE)`)
  - `UNIT_VALUE_FIELDS: tuple[str, ...] = ("sura_id", "ayah_id", "word_id", "page_no", "from_ayah_id", "to_ayah_id", "from_word_id", "to_word_id")`
  - `unit_key_of(values: Sequence[int | None]) -> int` — values in `UNIT_VALUE_FIELDS` order; first non-null single unit, else the encoded ayah pair, else the encoded word pair.
  - `unit_key_expression() -> Coalesce` — SQL twin of `unit_key_of`, `output_field=BigIntegerField()`; the pair parts are `Cast(F("from_ayah_id"), BigIntegerField()) * GROUP_KEY_BASE + F("to_ayah_id")` (same for words). Cast is required: `smallint * 1_000_000` overflows `int4`.
  - `unit_q(unit_ids: Iterable[int]) -> Q` — matches entry/change rows of any template: `sura_id__in | ayah_id__in | word_id__in | page_no__in` over the ids `< GROUP_KEY_BASE`, OR one `Q(from_ayah_id=f, to_ayah_id=t) | Q(from_word_id=f, to_word_id=t)` per id `>= GROUP_KEY_BASE`.
- Produces (`apps/content/models.py`):
  - `AssetTemplateChoice.AYAH_GROUP = "ayah_group"`, `AssetTemplateChoice.WORD_GROUP = "word_group"`
  - `GROUP_TEMPLATES: frozenset[str] = frozenset({AYAH_GROUP, WORD_GROUP})` (module level, after the choice)
  - On both `AssetVersionEntry` and `AssetVersionChange`: `from_ayah`, `to_ayah` (FK `quran.Ayah`), `from_word`, `to_word` (FK `quran.Word`), all `null=True, blank=True, on_delete=PROTECT, related_name="+"`, help_text `"Range start/end — set only for ayah-group-template assets"` / `"…word-group…"`.
  - `unit_id` property on both returns `unit_key_of(...)` of its own field values (replace the if-chain).
- Produces (`apps/content/tests/group_quran_data.py`): `GroupQuranDataMixin.bake_group_quran()` baking exactly: sura 1 (`ayas_count=3`), sura 2 (`ayas_count=2`); ayahs id 1–5 = (1:1, 1:2, 1:3, 2:1, 2:2) with text `"a1"`…`"a5"`; words id 1–8: ayah 1 → words 1,2,3 (positions 1–3), ayah 2 → 4,5, ayah 3 → 6, ayah 4 → 7,8; text `"w1"`…`"w8"`. Attributes `self.ayahs` (list, index 0 = id 1) and `self.words`. Docstring warns later tasks assert these counts.

- [ ] **Step 1: Write the failing tests** in `apps/content/tests/models/test_group_units.py` (class `GroupUnitModelTests(GroupQuranDataMixin, BaseTestCase)`):
  - `test_encode_group_key_where_round_tripped_should_return_from_and_to`: `decode_group_key(encode_group_key(4, 77431)) == (4, 77431)`; `encode_group_key(1, 5) < encode_group_key(2, 2)`; `encode_group_key(1, 2) < encode_group_key(1, 5)`.
  - `test_unit_id_where_ayah_range_entry_should_return_encoded_key`: entry with `from_ayah_id=1, to_ayah_id=3` → `unit_id == 1_000_003`.
  - `test_unit_id_where_word_range_change_should_return_encoded_key`: change with `from_word_id=6, to_word_id=7` → `6_000_007`.
  - `test_save_where_two_ranges_start_at_same_ayah_should_store_both`: entries (1→3) and (1→1) in the same version/column both save.
  - `test_save_where_same_range_twice_in_one_column_should_raise_integrity_error`.
  - `test_save_where_range_end_before_start_should_raise_integrity_error`: `from_ayah_id=3, to_ayah_id=1`.
  - `test_save_where_ayah_range_and_ayah_both_set_should_raise_integrity_error`.
  - `test_save_where_only_from_ayah_set_should_raise_integrity_error`.
  - `test_unit_key_expression_where_annotated_should_match_unit_id`: annotate entries of all kinds (one `ayah`, one ayah range, one word range) with `unit_key_expression()` and assert each equals `entry.unit_id`.
  - `test_unit_q_where_mixed_ids_should_match_only_those_rows`.
  - `test_asset_template_choice_where_group_values_should_have_labels`: `AssetTemplateChoice("ayah_group").label == "Ayah-group based"`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest apps/content/tests/models/test_group_units.py --create-db -q; git checkout -q uv.lock`
Expected: errors importing `apps.content.unit_keys` / `GroupQuranDataMixin`.

- [ ] **Step 3: Implement** `unit_keys.py`, the choice values, `GROUP_TEMPLATES`, the eight fields, and the constraints on both models:
  - Replace `entry_exactly_one_unit` / `change_exactly_one_unit` with six branches: each of the four single units alone, `from_ayah & to_ayah` set with all else null, `from_word & to_word` set with all else null.
  - Add `unique_entry_per_version_ayah_range_column (version, from_ayah, to_ayah, column)`, `unique_entry_per_version_word_range_column (version, from_word, to_word, column)` and `change_` twins.
  - Add check `entry_ayah_range_ordered`: `Q(from_ayah__isnull=True) | Q(from_ayah__lte=F("to_ayah"))`, `entry_word_range_ordered` likewise, and `change_` twins.
  - Update the `AssetVersionEntry` docstring (the unit is "a sura, an ayah, a word, a mushaf page, or a range of ayahs / words").

- [ ] **Step 4: Generate the migration** with the `DB_NAME=nonexistent_mm …makemigrations content --name group_templates` command; check it only adds fields/constraints and alters `template` choices, nothing else.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest apps/content/tests/models/ -q; git checkout -q uv.lock`
Expected: all pass, including the existing model tests.

---

### Task 2: `UnitSpec` for group templates

**Files:**
- Modify: `apps/content/services/asset_templates.py`
- Test: `apps/content/tests/services/test_asset_templates_groups.py`

**Interfaces:**
- Consumes: Task 1 (`encode_group_key`, `decode_group_key`, `GROUP_TEMPLATES`, range fields).
- Produces (all on `UnitSpec` unless noted):
  - `UnitSpec.field` for groups is the range prefix: `"ayah_range"` / `"word_range"`; `fk_field=None`. Add `is_group: bool` property (`template in GROUP_TEMPLATES`) and `range_fields -> tuple[str, str]` (`("from_ayah_id", "to_ayah_id")` / `("from_word_id", "to_word_id")`; raise `ValueError` on single templates).
  - `unit_columns(unit_id: int) -> dict[str, int]` — the model kwargs that store `unit_id`: `{"ayah_id": 7}`, `{"page_no": 3}`, or `{"from_ayah_id": f, "to_ayah_id": t}`. Replaces every `**{unit_field: unit_id}` in later tasks.
  - `entries_q(unit_ids: Sequence[int]) -> Q` — narrows an entry/change queryset to these units (single: `{field}__in`; group: OR of pair `Q`s; empty list → `Q(pk__in=[])`).
  - `order_for(unit_id: int) -> int` — single: `unit_id`; group: the `from` id (`order` is int4 — an encoded key would overflow).
  - `valid_unit_ids(asset, candidates)` for groups: a candidate is valid when both decoded ids exist (one `Ayah`/`Word` `id__in` query for all ends) and `from <= to`.
  - `UnitRow` gains `group_from: tuple[int, ...] | None = None`, `group_to: tuple[int, ...] | None = None` (`(sura, ayah)` or `(sura, ayah, word)`) and `orphaned: bool = False`.
  - Module function `group_label(template: str, start: Ayah | Word, end: Ayah | Word) -> str`: `"2:1 → 2:5"` (ayah) / `"2:255:1 → 2:255:4"` (word); a single-unit range is just `"2:3"` / `"2:255:1"`. Used by the read path, the diff and review (Tasks 3, 4).
  - `REFERENCE_TEXT_LIMIT = 500`: a group row's `reference_text` is the covered ayah texts (joined by `" "`) or word texts, cut at 500 characters with a trailing `"…"`.
  - `units_page(...)` for groups:
    - Ranges come from `source_version` when it is not `None` (a translated language: its rows are the source head's ranges) else from `version`; with no version at all (empty) → `([], 0)`.
    - Keys = distinct `(from, to)` pairs of the range version's entries; for a translated language also the version's own pairs **not** in the source → `orphaned=True`. Sorted by key.
    - `sura` param and the `surah`/`sura`/`aya` filters test the **from** position; `reference_text` filter tests the from unit's text; `cells` / `source_cells` filters are evaluated in Python with `ColumnFilter.matches` over one `values_list(from, to, text)` query per filtered column (like `_filter_pages`).
    - `total` = filtered key count; the page window is cut before any `UnitRow` is built; building the window's rows costs a constant number of queries (one `in_bulk` for all ends, one query for all covered units of the window via OR'd `id__range` `Q`s).
    - `label` via `group_label`, `sura`/`aya` = from position, `order` = encoded key (fits the `int` schema; it is never stored).
  - `total(asset)` for groups is not meaningful: return `0` and document that callers use `units_page`'s total.

- [ ] **Step 1: Write the failing tests** (`class GroupUnitSpecTests(GroupQuranDataMixin, BaseTestCase)`, tafsir asset with `template=ayah_group` / `word_group`, published source version + entries baked directly):
  - `test_units_page_where_ayah_group_source_should_list_stored_ranges_in_order`: entries (1→3, "x"), (1→1, "y"), (4→5, "z") → labels `["1:1", "1:1 → 1:3", "2:1 → 2:2"]`, `total == 3`.
  - `test_units_page_where_group_has_two_columns_should_list_range_once`.
  - `test_units_page_where_translation_should_list_source_ranges_and_flag_orphans`: source has (1→3); translation version has (1→3) and (4→4) → two rows, `(4→4).orphaned is True`, `(1→3).orphaned is False`.
  - `test_units_page_where_word_group_crosses_ayah_should_join_reference_text`: (3→4) on words → `reference_text == "w3 w4"`, `label == "1:1:3 → 1:2:1"`, `group_from == (1, 1, 3)`, `group_to == (1, 2, 1)`.
  - `test_units_page_where_reference_text_long_should_truncate_to_limit`.
  - `test_units_page_where_sura_filter_should_match_from_position`: (3→4 ayahs, i.e. 1:3→2:1) appears for `sura=1`, not for `sura=2`.
  - `test_units_page_where_cell_filter_should_filter_before_paging`.
  - `test_units_page_where_page_of_groups_should_use_constant_queries`: `assertNumQueries` equal for 2 and 20 groups.
  - `test_valid_unit_ids_where_group_candidates_should_reject_missing_and_reversed`: `encode(1,3)` valid, `encode(3,1)` invalid, `encode(1,99)` invalid.
  - `test_unit_columns_where_group_key_should_return_range_kwargs`, `test_entries_q_where_group_keys_should_match_only_those_ranges`, `test_order_for_where_group_key_should_return_from_id`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest apps/content/tests/services/test_asset_templates_groups.py -q; git checkout -q uv.lock`
Expected: FAIL (`KeyError` in `_SPECS` / missing attributes).

- [ ] **Step 3: Implement** the group branches; register `_SPECS[AYAH_GROUP] = UnitSpec(AYAH_GROUP, "ayah_range", None)` and `_SPECS[WORD_GROUP] = UnitSpec(WORD_GROUP, "word_range", None)`. Keep the module docstring rule (only this module branches on template) and extend it to name the group templates.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest apps/content/tests/services/test_asset_templates*.py -q; git checkout -q uv.lock`
Expected: PASS (new and existing).

---

### Task 3: Content repository and diff pipeline keyed by group

**Files:**
- Modify: `apps/content/repositories/asset_content.py`
- Test: `apps/content/tests/services/test_asset_content_groups.py`

**Interfaces:**
- Consumes: Task 1 (`unit_key_of`, `UNIT_VALUE_FIELDS`), Task 2 (`unit_columns`, `entries_q`, `order_for`, `group_label`, `is_group`).
- Produces: no new public names; these become group-aware:
  - `_cell_rows`: `values_list(*UNIT_VALUE_FIELDS, "column__key", "text")` and `unit_key_of(row[:8])`.
  - `entry_cells` → `version.entries.filter(spec.entries_q(unit_ids))`.
  - `create_draft_seeded_from` (non-mushaf branch), `replace_entries_from_parsed`, `upsert_entries`, `_record_changes`, `ensure_entries`, `restore_version`: build rows with `**spec.unit_columns(unit_id)` and `order=spec.order_for(unit_id)` (replacing `order=unit_id` and `order=orders.get(unit_id, unit_id)` fallbacks). `upsert_entries` keys `existing` by `(entry.unit_id, entry.column_id)` and filters with `spec.entries_q`.
  - `_units_by_id` for groups returns `{key: (start, end)}` (one `in_bulk` over all decoded ends, `select_related("ayah")` for words); `_change_to_dict` labels groups with `group_label`.
  - `version_diff`: `select_related` also `"from_ayah", "to_ayah", "from_word__ayah", "to_word__ayah"`; the unit object for a group change is `(change.from_x, change.to_x)`.
  - `get_pending_changes` / `publish_draft` already drop `text=""` cells: no change, but covered by a test.

- [ ] **Step 1: Write the failing tests** (`class GroupContentRepositoryTests(GroupQuranDataMixin, BaseTestCase)`):
  - `test_publish_draft_where_group_text_changed_should_record_modified`.
  - `test_publish_draft_where_group_range_moved_should_record_removed_and_added`: head (1→3,"t"); draft (1→2,"t") → one `REMOVED` at `from_ayah_id=1,to_ayah_id=3`, one `ADDED` at `1→2`.
  - `test_publish_draft_where_two_groups_start_at_same_ayah_should_record_both_added`.
  - `test_publish_draft_where_last_text_cleared_should_record_removed`: draft cell text `""` → `REMOVED`, and the committed version has no entry for that range.
  - `test_reconstruct_entries_where_group_version_pruned_should_rebuild_ranges`: commit v1, commit v2 (prunes v1), `reconstruct_entries(v1)` equals v1's snapshot keyed by encoded ids.
  - `test_restore_version_where_group_asset_should_restore_ranges`.
  - `test_create_draft_seeded_from_where_group_head_should_copy_ranges`.
  - `test_version_diff_where_group_changes_should_label_ranges`: labels `"1:1 → 1:3"`; `unit_id` encoded.
  - `test_upsert_entries_where_existing_group_cell_should_update_not_duplicate`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest apps/content/tests/services/test_asset_content_groups.py -q; git checkout -q uv.lock`
Expected: FAIL (writes put the encoded key into a missing column / `KeyError` on labels).

- [ ] **Step 3: Implement** the changes listed in Interfaces.

- [ ] **Step 4: Run the tests plus the existing content suites**

Run: `uv run pytest apps/content/tests/services apps/content/tests/portal -q; git checkout -q uv.lock`
Expected: PASS (no regressions on single-unit templates).

---

### Task 4: CSV header, export and blank template for groups

**Files:**
- Modify: `apps/content/columns.py`
- Modify: `apps/content/repositories/asset_content.py` (`_units_to_csv_bytes`)
- Test: `apps/content/tests/services/test_asset_content_export_groups.py`

**Interfaces:**
- Consumes: Task 2 (`decode_group_key` via spec, `REFERENCE_TEXT_LIMIT` is **not** applied to exports).
- Produces (`apps/content/columns.py`):
  - `RANGE_HEADERS_BY_TEMPLATE`: `ayah_group → ["from_surah", "from_ayah", "to_surah", "to_ayah"]`, `word_group → ["from_surah", "from_ayah", "from_word", "to_surah", "to_ayah", "to_word"]`; merged into `_UNIT_HEADER_BY_TEMPLATE`.
  - `REFERENCE_TEXT_HEADER = "reference_text"`.
  - `UNIT_HEADERS` also contains every range header and `reference_text` (column keys may not shadow them).
  - `csv_header(template, keys, verbose=True)` for a group template → range headers + `["reference_text"]` + keys; lean → range headers + keys.
- `_units_to_csv_bytes` for groups writes one row per **key present in `cells`** (with any non-blank text), sorted by key — never a canonical unit list — so `blank_template_csv_bytes` for a group template is the header row only. Verbose rows carry the full covered text (not truncated). Ends are resolved with one query per export (`in_bulk` of all decoded ends) and covered text with one query for all covered ids (ayah/word `id__range` OR'd), not per row.

- [ ] **Step 1: Write the failing tests:**
  - `test_entries_to_csv_bytes_where_ayah_group_should_write_range_rows_sorted`: entries (4→5,"c"), (1→3,"a"), (1→1,"b") → lines `from_surah,from_ayah,to_surah,to_ayah,text` / `1,1,1,1,b` / `1,1,1,3,a` / `2,1,2,2,c`.
  - `test_entries_to_csv_bytes_where_word_group_verbose_should_add_reference_text`: header `from_surah,from_ayah,from_word,to_surah,to_ayah,to_word,reference_text,text`; row for words 3→4 has `reference_text == "w3 w4"`.
  - `test_blank_template_csv_bytes_where_group_template_should_return_header_only`.
  - `test_entries_to_csv_bytes_where_multi_column_group_should_write_each_column`.
  - `test_validate_column_key_where_key_is_reference_text_should_raise`.
  - `test_entries_to_csv_bytes_where_many_groups_should_use_constant_queries`.

- [ ] **Step 2: Run to verify they fail.** `uv run pytest apps/content/tests/services/test_asset_content_export_groups.py -q; git checkout -q uv.lock` → FAIL.

- [ ] **Step 3: Implement.**

- [ ] **Step 4: Run** the new file and `apps/content/tests/services/test_asset_content_export_templates.py apps/content/tests/portal/test_csv_template.py apps/content/tests/portal/test_full_unit_exports.py`. Expected: PASS.

---

### Task 5: Review queue and gallery file-structure for groups

**Files:**
- Modify: `apps/content/repositories/asset_review.py` (`_unit_key`, `changes_for` select_related)
- Modify: `apps/content/api/portal/asset_review.py` (`resolve_label`)
- Modify: `apps/content/repositories/asset_columns.py` (`first_units_with_text`, `cells_for_units`, `unit_header_values`)
- Test: `apps/content/tests/services/test_asset_review_groups.py`, `apps/content/tests/internal/test_asset_file_structure_groups.py`

**Interfaces:**
- Consumes: `unit_key_expression`, `unit_q`, `unit_key_of`, `UNIT_VALUE_FIELDS` (Task 1); `group_label` (Task 2); `csv_header` group headers (Task 4).
- Produces:
  - `AssetReviewRepository._unit_key()` returns `unit_key_expression()`; `changes_for` also `select_related("from_ayah", "to_ayah", "from_word__ayah", "to_word__ayah")`.
  - Review `resolve_label` covers groups with `group_label(obj.version.asset.template, start, end)` (the asset is already selected).
  - `first_units_with_text` orders by `"order", *UNIT_VALUE_FIELDS` and keys rows with `unit_key_of`; `cells_for_units` filters with `unit_q`; `unit_header_values` returns the lean group header values `[from_surah, from_ayah, to_surah, to_ayah]` / `[from_surah, from_ayah, from_word, to_surah, to_ayah, to_word]` as strings (one `in_bulk` for all ends).

- [ ] **Step 1: Write the failing tests:**
  - `test_pending_cells_by_version_where_overlapping_groups_should_count_each`: two unreviewed group changes starting at the same ayah → pending count 2.
  - `test_list_review_changes_where_group_change_should_return_range_label` (portal API; assert `label == "1:1 → 1:3"`, `unit_id == 1_000_003`).
  - `test_changes_for_where_group_changes_should_use_constant_queries` (`assertNumQueries` same for 2 and 10 changes).
  - `test_asset_file_structure_where_ayah_group_tafsir_should_return_range_header_and_rows`: `header == ["from_surah", "from_ayah", "to_surah", "to_ayah", "text"]`, first row `["1", "1", "1", "3", "…"]`, `template == "ayah_group"`.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest apps/content/tests/services/test_asset_review_groups.py apps/content/tests/internal/test_asset_file_structure_groups.py -q; git checkout -q uv.lock`
Expected: FAIL.

- [ ] **Step 3: Implement** the Interfaces changes.

- [ ] **Step 4: Run** the two new files plus `apps/content/tests/services/test_asset_review.py apps/content/tests/portal/test_asset_review*.py apps/content/tests/internal/test_asset_file_structure.py`. Expected: PASS.

---

### Task 6: Strict import of group files, with source-range check

**Files:**
- Modify: `apps/content/services/asset_content_import.py`
- Modify: `apps/content/services/asset_content.py` (`import_uploaded_file_into_entries`, `import_file_into_version`, the `content_file_invalid_rows` message)
- Test: `apps/content/tests/services/test_asset_content_import_groups.py`

**Interfaces:**
- Consumes: Task 4 (`RANGE_HEADERS_BY_TEMPLATE`, `REFERENCE_TEXT_HEADER`), Task 2 (`valid_unit_ids`), Task 1 (`encode_group_key`).
- Produces:
  - `parse_content_file(raw, spec, asset, *, column_keys=None, strict=False, allowed_unit_ids: set[int] | None = None) -> list[ParsedEntry]`. For group templates parsing is **always strict** (`strict = strict or spec.is_group`). `ParsedEntry.unit_id` is the encoded key.
  - New row-problem reasons (module constants next to `UNKNOWN_UNIT`): `RANGE_REVERSED = "range_reversed"`, `NOT_IN_SOURCE = "not_in_source"`. Group files flag **any** repeated range as `DUPLICATE` (not only conflicting text). A range whose end comes before its start is `RANGE_REVERSED`; a position that does not exist is `UNKNOWN_UNIT`; with `allowed_unit_ids` given, a valid range outside it is `NOT_IN_SOURCE`.
  - Header detection for groups needs all range headers (exact names, case-insensitive) plus a text header; `reference_text` and unknown columns are ignored.
  - `import_uploaded_file_into_entries(version, *, strict=False)`: for a group asset whose `version.asset_language` is not the source, passes `allowed_unit_ids` = the keys of the source head (`asset.get_latest_version(asset.language)`, via `AssetContentRepository().reconstruct_entries`); no source head → every row is `NOT_IN_SOURCE`.
  - The `content_file_invalid_rows` message names the new reasons: extend it to `"Some rows can't be used: they repeat a unit or range, name a unit that doesn't exist, end before they start, use a range the source language doesn't have, or can't be read. Fix row(s) {rows} and upload again."` (update the Arabic translation). `extra["rows"]` keeps mapping row → reason.

- [ ] **Step 1: Write the failing tests:**
  - `test_parse_content_file_where_ayah_group_file_should_return_encoded_ranges`: rows `1,1,1,3,a` and `1,1,1,1,b` → `{encode(1,3): {"text": "a"}, encode(1,1): {"text": "b"}}`.
  - `test_parse_content_file_where_word_group_crosses_ayah_should_resolve`: `1,1,3,1,2,1,x` → `encode(3,4)`.
  - `test_parse_content_file_where_rows_out_of_order_should_accept_all`.
  - `test_parse_content_file_where_overlapping_ranges_should_accept_both`.
  - `test_parse_content_file_where_range_reversed_should_raise_with_row_number`: `exc.rows == {3: "range_reversed"}`.
  - `test_parse_content_file_where_unknown_position_should_raise_with_row_number`: `1,1,1,9,x` → `"unknown_unit"`.
  - `test_parse_content_file_where_same_range_repeated_should_raise_duplicate` (even with identical text).
  - `test_parse_content_file_where_not_strict_and_group_should_still_raise` (lenient callers cannot drop rows of a group file).
  - `test_parse_content_file_where_range_not_in_allowed_should_raise_not_in_source`.
  - `test_parse_content_file_where_verbose_export_reimported_should_match_cells` (round-trip with `reference_text`).
  - `test_create_tafsir_version_where_translation_language_uses_unknown_range_should_return_400` (portal upload; `error_name == "content_file_invalid_rows"`, `extra.rows` names the row with `"not_in_source"`).

- [ ] **Step 2: Run to verify they fail.** → FAIL.

- [ ] **Step 3: Implement** `_find_group_header_row`, `_group_column_map`, `_parse_group_entries` (keyed by the raw `(from…, to…)` tuple) and the resolution branch in `parse_content_file` (ayah ends via `_ayah_id_by_sura_aya`; word ends via `_word_id_by_sura_aya_position`, built once per import). Update the module docstring with the two group shapes.

- [ ] **Step 4: Run** the new file plus `apps/content/tests/services/test_asset_content_import*.py`. Expected: PASS.

---

### Task 7: Portal API — creation rules, group writes, translation rules, range preview

**Files:**
- Modify: `apps/content/services/translation.py` (create), `apps/content/api/portal/translations.py` (error union)
- Modify: `apps/content/services/asset_content.py` (`upsert_entries`, `publish_draft`, new group methods, `get_entries_page` rows)
- Modify: `apps/content/repositories/asset_content.py` (group write helpers)
- Modify: `apps/content/api/portal/asset_content.py` (`EntryOut`, `_entries_to_out`, new endpoints)
- Create: `apps/content/api/portal/quran_range.py` (preview endpoint) and register it on the portal router where `asset_content` is registered
- Test: `apps/content/tests/portal/test_asset_content_groups.py`, `apps/content/tests/portal/test_quran_range.py`, add to `apps/content/tests/portal/test_asset_template_create.py`

**Interfaces:**
- Consumes: Tasks 1–6.
- Produces (service, `AssetContentService`):
  - `add_group(slug, category, version_id, *, start: QuranPosition, end: QuranPosition, cells: dict[str, str], publisher_q=None) -> list[AssetVersionEntry]`
  - `move_group(slug, category, version_id, unit_id: int, *, start: QuranPosition, end: QuranPosition, publisher_q=None) -> list[AssetVersionEntry]` — moves every draft cell of the group to the new range in one transaction.
  - `delete_group(slug, category, version_id, unit_id: int, publisher_q=None) -> None`
  - `QuranPosition` = frozen dataclass `(surah: int, ayah: int, word: int | None = None)` in `asset_templates.py`, with `UnitSpec.key_for_range(start, end) -> int` (resolves positions to ids, raises `group_range_invalid` for a missing position / wrong word-ness / end before start).
- Rules (service):
  - Translation create with a group template → `400 template_not_allowed` (`_("Ayah-group and word-group templates are only available for tafsir.")`).
  - `add_group` / `move_group` / `delete_group` require a draft (`version_not_editable`), a group template (`400 template_not_grouped`), and the source language (`400 group_ranges_source_only`) — except `delete_group` on a translated language is allowed when the range is **orphaned** (not in the source head).
  - `add_group` / `move_group` to a range the draft already has → `400 group_exists`; `move_group` / `delete_group` on a key the draft lacks → `404 group_not_found`.
  - `upsert_entries` on a translated group language: every row's `unit_id` must be a source-head key → else `400 group_not_in_source`.
  - `publish_draft` on a translated group language: draft keys with non-blank text that the source head lacks → `400 orphaned_groups` with message `_("Move or delete the text of groups the source no longer has: {groups}.")` (labels via `group_label`, at most 10, `…` after) and `extra={"groups": [labels]}`.
  - `get_entries_page` passes the source head as `source_version` (already does) so Task 2's group branch lists source ranges; every row dict gains `group_from`, `group_to`, `orphaned`.
- Produces (API, all under `content/{category}/{slug}/versions/{version_id}/`):
  - `EntryOut` gains `group_from: QuranPositionOut | None = None`, `group_to: QuranPositionOut | None = None`, `orphaned: bool = False` (`QuranPositionOut {surah: int, ayah: int, word: int | None = None}`); `_entries_to_out` fills them for group entries (the patch response).
  - `POST groups/` body `GroupIn {start: QuranPositionIn, end: QuranPositionIn, cells: dict[str, str] = {}}` → `200 list[EntryOut]` (one row). Access `"content"`.
  - `PUT groups/{unit_id}/` body `GroupRangeIn {start, end}` → `200 list[EntryOut]`.
  - `DELETE groups/{unit_id}/` → `204`.
  - Error unions list `version_not_editable`, `template_not_grouped`, `group_ranges_source_only`, `group_range_invalid`, `group_exists`, `unknown_column` (400) and `group_not_found`, the category not-found names, `version_not_found` (404).
  - Publish endpoint error union adds `orphaned_groups`; PATCH entries adds `group_not_in_source`.
  - `GET /portal/content/quran-range/?from_surah=&from_ayah=&from_word=&to_surah=&to_ayah=&to_word=` (word params optional together) → `QuranRangeOut {units: list[QuranRangeUnitOut], truncated: bool}`, `QuranRangeUnitOut {surah, ayah, word: int | None, text}`; ayahs when the word params are absent, words otherwise; at most `QURAN_RANGE_LIMIT = 1000` units then `truncated=True`; invalid range → `400 group_range_invalid`. Auth: any portal user with `PORTAL_READ_TAFSIR` (`check_permission`). One query.

- [ ] **Step 1: Write the failing tests** (portal API, tafsir category, authenticated user with `PORTAL_EDIT_TAFSIR_CONTENT`, `PORTAL_READ_TAFSIR`, `PORTAL_ACCESS_ALL_LANGUAGES`):
  - `test_create_translation_where_group_template_should_return_400` (`template_not_allowed`); `test_create_tafsir_where_group_template_should_create`.
  - `test_add_group_where_source_draft_should_store_cells_and_return_row` (`group_from == {"surah": 1, "ayah": 1, "word": None}`, `label == "1:1 → 1:3"`).
  - `test_add_group_where_range_exists_should_return_400` (`group_exists`); `test_add_group_where_end_before_start_should_return_400` (`group_range_invalid`); `test_add_group_where_word_crosses_ayah_should_store`.
  - `test_add_group_where_translated_language_should_return_400` (`group_ranges_source_only`); `test_add_group_where_single_unit_template_should_return_400` (`template_not_grouped`).
  - `test_move_group_where_source_draft_should_move_every_column`; `test_move_group_where_unknown_key_should_return_404` (`group_not_found`).
  - `test_delete_group_where_source_draft_should_remove_cells`; `test_delete_group_where_translation_orphan_should_remove`; `test_delete_group_where_translation_non_orphan_should_return_400` (`group_ranges_source_only`).
  - `test_patch_entries_where_translation_range_not_in_source_should_return_400` (`group_not_in_source`).
  - `test_list_entries_where_translation_should_list_source_ranges_with_source_cells` (each row's `source_cells` is the source text for the same range; an orphan row has `orphaned: true`).
  - `test_publish_draft_where_translation_has_orphan_text_should_return_400` (`orphaned_groups`, `extra.groups == ["1:1 → 1:3"]`).
  - `test_list_entries_where_group_draft_cell_cleared_should_still_list_row` (row visible until commit).
  - `test_list_entries_where_groups_page_should_use_constant_queries`.
  - `test_quran_range_where_word_range_crosses_ayah_should_return_words_in_order`; `test_quran_range_where_ayah_range_should_return_ayahs`; `test_quran_range_where_over_limit_should_truncate`; `test_quran_range_where_reversed_should_return_400` (`group_range_invalid`); `test_quran_range_where_no_permission_should_return_403`.

- [ ] **Step 2: Run to verify they fail.** → FAIL.

- [ ] **Step 3: Implement** service rules (Service → Repository; repository gets `move_group_cells(version, spec, old_key, new_key) -> list[AssetVersionEntry]` and `delete_group_cells(version, spec, key) -> int`, both marking `content_edited`), schemas, endpoints and the preview router. Each multi-write path runs in `transaction.atomic()` and re-checks the draft under a row lock (`select_for_update`); a concurrent insert of the same range surfaces as `IntegrityError` on the unique constraint and is mapped to `group_exists`. Writes keep `simple_history` (`bulk_*_with_history`).

- [ ] **Step 4: Run** the new files plus `apps/content/tests/portal -q`. Expected: PASS.

---

### Task 8: Surfaces check, docs, localization, performance

**Files:**
- Test: `apps/content/tests/public/test_samples.py` (add one test)
- Modify: `docs/ARCHITECTURE.md` (templates paragraph ~line 268, ER diagram fields for `AssetVersionEntry`/`AssetVersionChange`, csv-template note ~line 281), `docs/PACKAGE_ARTIFACT.md` (line 38 "Granular per-ayah records" → per-unit or per-range)
- Modify: `locale/ar/LC_MESSAGES/django.po` (+ compiled `.mo`)

**Interfaces:** Consumes everything above. Produces no code.

- [ ] **Step 1: Write** `test_get_tafsir_sample_where_only_group_tafsir_exists_should_return_404` (`tafsir_not_found`; `get_ready_asset` picks ayah templates only). Run it; it passes without code changes (confirmation test).
- [ ] **Step 2: Consumer surfaces pass** (CLAUDE.md "Publishing and asset availability"): confirm no availability rule changed; list in the summary the surfaces checked (gallery detail/download, file-structure, package registry download via `store_generated_package_file`, samples, tenant/public APIs, new-version email, Dependabot) and that only file-structure and CSV generation needed changes.
- [ ] **Step 3: Docs.** Update the files above; keep mermaid in sync with the new fields. `docs-website/docs` has no tafsir CSV-shape page: no change, say so.
- [ ] **Step 4: Localization gate** (Global Constraints). Expected: `0 untranslated messages`.
- [ ] **Step 5: Performance.** For the entries GET, PATCH, group POST, export and review list, record query counts on the base branch (ayah template) vs this branch (ayah template and group template) with `CaptureQueriesContext`; group endpoints must be constant in the number of groups. Put the numbers in the summary.
- [ ] **Step 6: Full suite and hooks.** `uv run pytest -q -p no:cacheprovider; git checkout -q uv.lock` → all pass; per-file pre-commit loop → no `Failed`. Run the review-pitfalls checklist (multi-write endpoints atomic; check-then-create on the unique range wrapped against `IntegrityError` → `group_exists`).
- [ ] **Step 7: itqan-cli check.** `itqan-cli/src/itqan_cli/columns_comment.py` prints `CSV, one row per <template>`; confirm `one row per ayah_group` reads acceptably (no change) and note it.
