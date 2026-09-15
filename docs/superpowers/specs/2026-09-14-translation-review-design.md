# Translation review phase — design

**Date:** 2026-09-14
**Status:** Approved (design); implementation not started
**Scope:** Backend (`itqan-cms-backend`) + Frontend (`cms-frontend`)
**Depends on / lands after:** multi-language assets, commit-history/diffs
(`AssetVersionChange` deltas), and the per-language availability gate.

## Problem

The previous phase let editors add and edit translations, each publish producing
a commit whose per-ayah delta is stored as `AssetVersionChange` rows. Now those
changes must be **reviewed**: a reviewer works through the changes one by one and
either **approves** a change, leaves a **comment** (meaning "needs changes"), or
leaves it **unreviewed**. Reviewers **cannot edit** the translations themselves —
they only record a review outcome. Who approved a change (and when) must be
stored for **auditing**.

Reviewers only handle the languages **assigned** to them, and the review surface
is gated behind a dedicated **permission**.

## Chosen approach

Reviews attach to individual `AssetVersionChange` rows (the per-commit delta is
the review unit). Each change carries a single shared review state
(`unreviewed | approved | commented`) plus the auditing fields
(`reviewed_by`, `reviewed_at`) and the current `comment`. Reviewer↔language
assignment is stored per-language globally (`ReviewerLanguage`) and managed via
Django admin this phase. A single permission `PORTAL_REVIEW_CONTENT` gates the
whole review surface. The reviewer works in a consolidated per-`(asset, language)`
grid on the asset detail page.

**Rejected alternatives** (from brainstorming):
- Reviewing per-ayah *current text* instead of per-commit deltas — loses the tie
  to what actually changed and to the commit audit trail.
- Approve + free-floating comments as orthogonal fields — the user wants a
  comment to mean "needs changes", i.e. a state, so states are exclusive.
- One review per `(change, reviewer)` (multi-reviewer consensus) — unnecessary
  now; one shared state per change with `reviewed_by` is enough.
- Per-`(asset, language)` assignment and a portal assignment-management UI —
  heavier than needed; per-language-global + Django admin covers this phase.
- Gating publish/availability on approval — deferred; this phase is audit-only.

## Out of scope

- Publish / availability gating on review outcome (review is **audit-only**).
- A portal UI to manage reviewer↔language assignments (Django admin only).
- Multiple independent reviews per change / consensus.
- Comment threads (a single current comment per change).
- Notifications to editors when a change is commented.

## Data model

**New — `ReviewerLanguage`** (a reviewer's globally-assigned languages):
```
user      FK -> users.User (on_delete=CASCADE, related_name="reviewer_languages")
language  CharField(max_length=10)   # ISO code, e.g. "fr"
Meta.constraints: UniqueConstraint(fields=["user", "language"], name="unique_reviewer_language")
```
Managed via Django admin. A user with `PORTAL_REVIEW_CONTENT` but no
`ReviewerLanguage` rows can review nothing.

**New — `AssetVersionChangeReview`** (one review per change):
```
change       OneToOneField -> AssetVersionChange (on_delete=CASCADE, related_name="review")
state        CharField choices ReviewStateChoice: approved | commented
             (unreviewed is represented by the ABSENCE of a row)
comment      TextField(blank=True)          # required (non-empty) when state=commented
reviewed_by  FK -> users.User (on_delete=SET_NULL, null=True, related_name="+")
reviewed_at  DateTimeField                  # set on each action
```
`ReviewStateChoice` stores only the two acted states; "unreviewed" is the default
(no row). Setting a change back to unreviewed deletes the row. `reviewed_by` +
`reviewed_at` are the audit record ("who approved / commented, when").

**Invariant:** a change's effective state is `review.state` when a row exists,
else `unreviewed`.

**New permission** — `PermissionChoice.PORTAL_REVIEW_CONTENT`
(`"portal_review_content"`, "Portal - Review Content"). No implied-permission
entries (review is independent of read/update).

## The language of a change

A change's language is `change.version.asset_language.language` when set, else
`change.version.asset.language` (legacy source rows). Enforcement and the
language filter both use this resolution.

## Enforcement rules

A user may see or act on the review surface only if **all** hold:
1. They hold `PORTAL_REVIEW_CONTENT`.
2. The asset is within their tenant (`publisher_q`, as elsewhere).
3. The change's language ∈ their `ReviewerLanguage` set.

Additional rules:
- Reviewers get **no content-edit path** through this surface; the review API
  only writes review state/comment. Review permission is independent of
  `PORTAL_UPDATE_*` (a pure reviewer cannot edit translations).
- `state=commented` requires a non-empty `comment` → else
  `review_comment_required` (400).
- `state=approved` or `unreviewed` does not require a comment; the previous
  comment is cleared on approve, and the row is deleted on unreviewed.

## API (portal)

All under `/portal/`, tenant-scoped, requiring `PORTAL_REVIEW_CONTENT`.

- `GET content/{category}/{slug}/review/languages/`
  → `list[str]`: the asset's languages that intersect the caller's assigned
  languages (their pickable set for this asset).

- `GET content/{category}/{slug}/review/changes/?language=<code>&state=<filter>`
  → **paginated** (`results`/`count`) list of change rows for that language:
  `id, sura, aya, surah_name, change_type, old_text, new_text,
   commit_ref (version.name), commit_id, review_state, comment,
   reviewed_by (name|null), reviewed_at`.
  403 if the caller is not assigned that language. `state` filter is optional
  (`unreviewed|approved|commented`) for a worklist view. Ordered newest-commit
  first, then ayah order.

- `PATCH content/{category}/{slug}/review/changes/{change_id}/`
  body `{ "state": "approved|commented|unreviewed", "comment"?: str }`
  → the updated change review row. Validates permission, tenant, that the change
  belongs to this asset, and that its language ∈ the caller's assignment. Sets
  `reviewed_by = request.user`, `reviewed_at = now`. `commented` requires a
  comment; `unreviewed` deletes the review row.

Errors (localized, en + ar): `review_comment_required`,
`language_not_assigned` (403), plus the existing `*_not_found` /
`unsupported_content_category`.

## Frontend — consolidated review grid

On the asset detail page (tafsir + translation), a **Review** section shown only
when the user has `PORTAL_REVIEW_CONTENT`:
- **Language selector** limited to the caller's assigned languages for this asset
  (`review/languages/`). If empty, the section shows an "no assigned languages"
  note.
- **Grid**, one row per change: `surah:ayah`, change type badge, old→new text
  (stacked), the commit ref, the reviewed-by/at, the current comment, and a
  **state control** with three actions: **Approve**, **Comment** (opens a dialog
  to enter/edit the comment → sets `commented`), **Unreviewed** (clears).
- **State filter** (All / Unreviewed / Approved / Commented) as a worklist.
- Paginated. **Read-only on content** — no cell editing.
- New `AssetReviewService`, models, i18n (en + ar), permission gate via
  `AdminAuthService.hasPermission`.

The reviewer column/controls are only rendered with the permission — this is the
"specific permission to see the reviewer column".

## Auditing

`reviewed_by` + `reviewed_at` on each review row record who set the current state
and when. This satisfies "store who made the approval". A full per-action history
table is deliberately **not** added this phase (single current state + actor is
enough); it can be layered later without changing the surface.

## Testing

- Model: `ReviewerLanguage` uniqueness; `AssetVersionChangeReview` OneToOne;
  `commented` requires comment (service-level guard).
- Permission: no `PORTAL_REVIEW_CONTENT` → 403 on every review endpoint.
- Assignment: assigned language → 200; unassigned language → 403; the
  changes/languages endpoints only return assigned languages.
- State transitions: approve sets state+audit; comment requires text and stores
  it; unreviewed deletes the row; effective state defaults to unreviewed.
- Reviewer cannot edit content (no content mutation via the review surface).
- List: correct change fields, language filter, state filter, pagination,
  newest-commit-first ordering; changes on pruned commits still appear.
- Tenant isolation via `publisher_q`.
- Localization: all new strings translated (en + ar), 0 untranslated, compiles.

## Migration

- Additive only: two new tables + the new permission choice. No data migration.
- Existing changes have no review row → all start `unreviewed`, as intended.

## Sequencing note

Lands after the availability phase on the same feature line. Its own spec → plan
→ implementation. Audit-only, so it does not touch consumer serving, publishing,
or the availability gate.
