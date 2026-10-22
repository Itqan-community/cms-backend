# Multi-Column Text Assets — itqan-cli Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an entry in `itqan-assets.yaml` installs a multi-column asset, the CLI writes, and keeps current, a `# itqan:columns` comment block above that entry describing the CSV's columns.

**Architecture:** The registry now returns a `structure` object (template, CSV header, columns with labels) per catalog language and per resolved version. A pure module renders the block. `add`/`browse`/`init` write it from the catalog, and `install` refreshes it from what was actually resolved. Only lines carrying the marker are ever touched.

**Tech Stack:** Python, click, requests, pytest (`uv run pytest`).

**Spec:** `itqan-cms-backend-columns/docs/superpowers/specs/2026-10-21-multi-column-text-assets-design.md`
**Depends on:** backend plan Tasks 9–10 (`structure` on `/packages/` and resolve; the block format in `docs/ASSET_MANIFEST.md`).

## Global Constraints

- Work in a new worktree of `itqan-cli` branched with `git worktree add --no-track -b feat/multi-column-comments ../itqan-cli-columns origin/main`. Use the base branch the repo actually uses; check with `git remote show origin`.
- The block format is normative and must match the backend's `render_columns_comment` byte for byte:

  ```text
  <indent># itqan:columns CSV, one row per <template>: <header joined by ", ">
  <indent># itqan:columns   <key>: <label_en> / <label_ar>
  ```

  - Label lines use whichever labels exist (`en / ar`, or just one). A column with no labels gets no line.
  - The block is written only when there is more than one column. Otherwise an existing block is removed.
  - `<indent>` is the entry key's indentation. The block sits directly above the key.
  - Replacement touches only consecutive marker lines directly above the key.
- **Older registries:** a missing `structure` field means "unknown", and the CLI then leaves any block untouched. It never removes a block because of a missing field.
- No subset-selection (`columns:`) entry field in this plan.
- No Claude attribution in commits or PRs. Commits follow the repo's conventional style.

## Review Focus

1. **A hand-written comment directly above an entry.** It survives both add and install-refresh. Pinned in Task 1.
2. **An entry in flow style (`name: {version: "^1"}`), or quoted keys.** Inserting or refreshing the block still targets the right key, and a flow entry is left without a block rather than corrupted. Pinned in Task 1.
3. **Install where the registry predates `structure`.** The manifest bytes stay unchanged. Pinned in Task 3.
4. **An Arabic label.** Written as UTF-8. The manifest is re-read and stays valid. Pinned in Task 1.
5. **Install that fails mid-download.** The manifest is not rewritten. The refresh happens only after the lockfile write succeeds. Pinned in Task 3.

---

### Task 1: Render and replace the block

**Files:**
- Create: `src/itqan_cli/columns_comment.py`
- Test: `tests/test_columns_comment.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) PackageColumn(key: str, label_en: str = "", label_ar: str = "")`
  - `@dataclass(frozen=True, slots=True) PackageStructure(template: str, header: tuple[str, ...], columns: tuple[PackageColumn, ...])`
  - `MARKER = "# itqan:columns"`
  - `render_block(structure: PackageStructure, indent: str) -> list[str]` returns `[]` when `len(columns) <= 1`.
  - `replace_block(content: str, entry_name: str, lines: list[str]) -> str` finds the block-style key line for `entry_name` under `assets:` (quoted or bare; the same matching as `add.set_entry_version`). It removes the consecutive marker lines directly above that key and inserts `lines`. A flow-style entry, or an entry that isn't found, returns `content` unchanged. The result must parse with `parse_manifest_content`, otherwise it raises `ManifestError`.
- [ ] **Step 1: Failing tests.**
  - `render_block` for the Q&A structure (header `surah, ayah, question, answer`, labels `Question / السؤال` and `Answer / الجواب`) at indent `"  "` equals:
    ```
      # itqan:columns CSV, one row per ayah: surah, ayah, question, answer
      # itqan:columns   question: Question / السؤال
      # itqan:columns   answer: Answer / الجواب
    ```
  - A single column gives `[]`. A column without labels gives no label line.
  - `replace_block`:
    - inserts above the key
    - replaces an old block
    - keeps a user comment that sits above the block (Review Focus 1)
    - removes the block when given `[]`
    - leaves a flow entry unchanged (Review Focus 2)
    - works with quoted keys
    - round-trips an Arabic label (Review Focus 4)
- [ ] **Step 2:** `uv run pytest tests/test_columns_comment.py -q` FAILS.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: render and replace the itqan:columns comment block`.

---

### Task 2: Parse `structure` and write the block on add/browse/init

**Files:**
- Modify: `src/itqan_cli/client.py` (`CatalogLanguage`, `ResolvedAssetPayload`, catalog and resolve parsing), `src/itqan_cli/browse.py` (`NewEntry.lines` / `add_entries`), `src/itqan_cli/init_template.py` if `init` builds entries separately
- Test: extend `tests/test_client.py`, `tests/test_add.py`, `tests/test_browse.py`, `tests/test_init.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `CatalogLanguage.structure: PackageStructure | None = None` and `ResolvedAssetPayload.structure: PackageStructure | None = None`.
  - `parse_structure(raw: dict | None) -> PackageStructure | None` in `client.py`. A missing or `null` value gives `None`, and a malformed one raises `RegistryApiError`, like the other fields.
  - `NewEntry.lines(indent)` prepends `render_block(self.language.structure, indent)` when the structure is known.
- [ ] **Step 1: Failing tests.**
  - Catalog JSON with `structure` parses into the dataclass, and JSON without it gives `None`.
  - `itqan add qa --no-install` against a stubbed catalog writes the block above the new entry, and a single-column asset gets no block.
  - `browse` and `init` produce the same thing for a multi-column pick.
- [ ] **Step 2–4:** FAIL → implement → PASS (`uv run pytest -q`).
- [ ] **Step 5:** Commit `feat: describe multi-column assets in the manifest on add`.

---

### Task 3: Refresh on install

**Files:**
- Modify: `src/itqan_cli/main.py` (`_run_install`)
- Test: extend `tests/test_cli_integration.py`

**Interfaces:**
- Produces:
  - `refresh_blocks(content: str, payloads: list[ResolvedAssetPayload]) -> str` in `columns_comment.py`. For each payload whose `structure is not None`, it applies `replace_block(content, payload.entry_name, render_block(structure, indent))`. `indent` is the entry key's own indentation.
  - `_run_install` calls it **after** the lockfile has been written successfully, and writes the manifest only when the text changed. When it does, it prints `Updated column notes in <manifest>`.
- [ ] **Step 1: Failing tests.**
  - Install resolves a version whose structure gained a column, and the manifest block now lists it.
  - A registry response without `structure` leaves the manifest bytes unchanged (Review Focus 3).
  - A download failure leaves the manifest untouched (Review Focus 5).
  - No change means no write, which you can check through the file's mtime or bytes.
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5:** Update `README.md` (manifest section) and `CHANGELOG.md` (unreleased) to describe the block. Commit `feat: refresh column notes on install`.
