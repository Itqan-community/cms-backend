# Commit-style history with diffs & restore — design

**Date:** 2026-09-09
**Status:** Approved (design); implementation not started
**Scope:** Backend (`itqan-cms-backend`) + Frontend (`cms-frontend`)
**Depends on / lands after:** the multi-language assets work
(`2026-09-02-multilanguage-assets-design.md`) — this builds directly on
`AssetLanguage`, per-`(asset, language)` versions, per-ayah entries, and the
versions manager introduced there.

## Problem

Editors want to work in **batches** and record *why* each batch changed the
content — like git. Each batch is committed with a **required message**, produces
a new asset version whose description is that message, and the asset detail page
should show a **git-log-style history**: every commit, its **diff** (what changed
per ayah), with the ability to **download** or **restore** any past commit.

Editors expect **hundreds of commits per language** over an asset's life, so full
snapshots per commit would balloon storage — commits must be stored as **deltas**.

## Chosen approach (Approach A): head snapshot + per-commit deltas

A commit is one published `AssetVersion` (per language) — reusing the existing
versioning. Its message is the (now required) description. Each commit stores its
**delta from its predecessor** as `AssetVersionChange` rows (the stored diff).
Only the **head** (latest commit per language) keeps full `AssetVersionEntry` +
`file_url`; older commits keep only their deltas. Download/restore of a past
commit **replay deltas** into a full snapshot.

Rejected: **B (pure deltas, no head snapshot)** — rewrites consumer serving and
reconstructs on every read for little extra gain. **C (full snapshots + stored
diffs)** — simplest but storage = snapshots *plus* deltas, defeating the goal.

Approach A meets the delta-storage goal, makes diffs first-class (stored), and
leaves consumer serving, the public/tenant APIs, and the ag-grid editor untouched
(they only ever read the head).

**Out of scope:** whole-asset time-travel (rolling *all* languages back to a
moment). Commits, diffs, and restore are **per-language**.

## Current state this builds on

- `AssetVersion` (per `asset` + `asset_language`, `state` draft/published,
  `name`, `summary`, `created_by`, `content_edited`, `file_url`, `size_bytes`).
  One draft per `(asset, language)`; `get_latest_version(language)` = latest
  published (the "active" version / head).
- `AssetVersionEntry` (version FK, ayah FK, text, order) — full per-ayah content.
- Draft flow: get-or-create draft (seeded from head + mushaf top-up for
  translations) → edit entries → `publish_draft` (drops empty rows, generates the
  CSV file). Restore endpoint duplicates a version's content into a new active one.
- Versions manager (asset detail, per-language) lists published versions with
  `is_active`, download, and restore.

## Data model

**Reused:**
- `AssetVersion` = **a commit**. `summary` = the **required commit message**;
  `name` = auto short-ref (`v1`, `v2`, …); `created_by` = author;
  `created_at` = commit time. `file_url`/full `AssetVersionEntry` kept **only on
  the head** and the draft.

**New — `AssetVersionChange` (stored delta / diff):**
```
version       FK -> AssetVersion (related_name="changes", on_delete=CASCADE)
ayah          FK -> quran.Ayah (on_delete=PROTECT, related_name="+")
change_type   CharField choices: added | modified | removed
old_text      TextField(blank=True)   # "" for added
new_text      TextField(blank=True)   # "" for removed
order         PositiveIntegerField    # ayah index, for display ordering
Meta.constraints: UniqueConstraint(fields=["version", "ayah"], name="unique_change_per_version_ayah")
Meta.indexes: Index(fields=["version", "order"])
```
Each row is one changed ayah, representing predecessor → this commit for the
language. First commit: all rows `added`.

**Invariants:**
- Every *new* commit has a complete `AssetVersionChange` set (its diff).
- Only the head keeps full `AssetVersionEntry` (+ `file_url`); superseded commits
  keep only deltas.
- The draft keeps full entries (working copy).
- Legacy (pre-feature) commits keep their full entries and have **no** change
  rows — handled by dual-mode read paths below.

## Commit flow (publish)

Editor: **Save & publish → Commit**. Opens a **Commit dialog**:
- **required** message field;
- **change review**: counts + changed-ayah refs (`~2:5 ~2:7 +2:6 −2:9`), computed
  from the pending diff (draft entries vs head entries).

`publish_draft` (extended), given a required `message`:
1. Compute the delta head-entries → draft-entries per ayah:
   - `added` — non-empty in draft, absent/empty in head;
   - `removed` — non-empty in head, empty/absent in draft;
   - `modified` — present in both, text differs.
2. Guards: empty delta → `no_changes_to_publish` (exists); blank message →
   `commit_message_required` (400).
3. Draft becomes the new head: keep full entries (drop empty rows as today),
   generate `file_url` CSV, set `summary = message`.
4. Store the delta as `AssetVersionChange` rows on the new commit.
5. Prune the previous head: delete its full `AssetVersionEntry` and clear its
   `file_url` (its own delta was stored when it was committed; historical
   downloads reconstruct on demand).

First commit (no head): delta = every entry as `added`.

## History (commit log) + diff

**Backend:**
- History list = existing per-language versions list; add `created_by` (author)
  and `change_counts` (added/modified/removed tallies) for the log summary.
- `GET content/{category}/{slug}/versions/{id}/diff/` — **paginated**; returns
  changed ayahs (`sura`, `aya`, `surah_name`, `change_type`, `old_text`,
  `new_text`). **Dual-mode**: stored `AssetVersionChange` if present; otherwise
  compute from this commit's entries vs its predecessor's (legacy commits).

**Frontend** — the versions manager (per-language) becomes the **commit log**:
- Each row: short-ref, message, author, date, `Active` badge, compact change
  summary (`+1 ~3 −1`).
- Expand a row → lazy-loads its diff into an inline panel; each changed ayah shown
  as `sura:aya` + marker + stacked old/new text (paginated — an import/first
  commit can touch thousands of ayahs).
- Row actions: **Download** (reconstructs for non-head commits), **Restore**.

## Reconstruction, download, restore

- `reconstruct_entries(version)`: if the commit has full entries (head or legacy)
  → use them; else fold deltas `1..N` (added/modified set text, removed drop) into
  a `{ayah_id: text}` snapshot.
- Historical **download**: export endpoint reconstructs when entries are absent,
  then reuses the existing CSV serializer (lean + verbose).
- **Restore N**: reconstruct N → run through the normal commit path (delta vs
  current head, stored; becomes new head + file), auto message `Restore of {ref}`
  (editable). Adapts the existing restore endpoint to reconstruct rather than copy
  pruned entries.

## Migration (low-risk)

- Schema-only: add `AssetVersionChange`. **No destructive data migration.**
- **Dual-mode** read paths: new commits use stored deltas + pruning; pre-existing
  commits keep full entries and get diff/reconstruction computed from snapshots on
  the fly. The feature works for all history immediately; storage savings apply
  going forward; no risky backfill.

## Testing

- Delta computed correctly (added/modified/removed; first commit all-added).
- Old head pruned (entries + file cleared) while head keeps entries + file.
- Diff endpoint dual-mode: stored delta for new commits; computed for legacy.
- Reconstruction folds deltas to the correct snapshot; equals head entries for the
  head; equals a legacy commit's own entries.
- Historical download reconstructs the correct CSV (lean + verbose columns).
- Restore reconstructs a past commit → new active commit with its content.
- Commit message required → 400 when blank; empty diff → `no_changes_to_publish`.
- Consumer serving / samples / public download unaffected (still read the head).
- Migration adds the table with no data loss.

## Sequencing note

This must land **after** the multi-language PR merges (it builds on that model).
Recommended: its own branch off `staging` once multi-language is merged, its own
spec → plan → PR — not stacked on the open multi-language branch.
