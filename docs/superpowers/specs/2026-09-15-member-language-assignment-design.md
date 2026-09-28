# Member Language Assignment — Design

**Status:** approved
**Date:** 2026-09-15
**Supersedes (partially):** `2026-09-14-translation-review-design.md` — the reviewer-language
assignment defined there is generalised here to cover editing as well.

## Goal

Editors, like reviewers, work only in the languages assigned to their publisher membership.
Add a permission that bypasses assignment entirely (for admins and oversight roles), and put
"add a new language to an asset" behind its own permission.

## Background

Three facts about the code as it stands today shaped this design:

1. `GET /portal/content/{category}/{slug}/languages/` applies **no** assignment filter — every
   member with read access sees every language on an asset.
2. `POST .../languages/` (add language) is gated by `write=True`, i.e. the *same* permission as
   editing content (`PORTAL_UPDATE_TRANSLATION` / `PORTAL_UPDATE_TAFSIR`). It is not separately
   controllable.
3. The two seeded groups — `Publisher Member`, `Publisher Member Admin` — hold **no** content-edit
   permissions. Today's editors obtain `PORTAL_UPDATE_*` through custom per-deployment groups or
   through `Itqan Internal`. Any rollout keyed on seeded group *names* would therefore miss every
   real editor.

`ReviewerLanguage` currently exists in `apps/publishers/models.py` (moved there from `content`
earlier in this branch) with the semantics *"no rows = review nothing"*.

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | One shared language set per member, not per role | A member's assignment answers "which languages do you work in"; their permissions answer "what may you do there". Avoids a `role` column, a doubled UI, and a role filter on every query. |
| 2 | `PORTAL_ACCESS_ALL_LANGUAGES` is a full bypass (see **and** act) | Holder is treated as assigned to every language on the asset. What they may do is still governed by `PORTAL_UPDATE_*` / `PORTAL_REVIEW_CONTENT`. A view-only bypass would create a read-only state the editor UI must render and explain. |
| 3 | One `PORTAL_ADD_ASSET_LANGUAGE` for both categories | Adding a language is the same act for a translation and a tafsir; matches how `PORTAL_REVIEW_CONTENT` is scoped. |
| 4 | Rollout grants the bypass to groups holding a content-edit permission | Data-driven, so it covers custom groups (see Background #3). Preserves exactly today's behaviour for exactly today's editors. |
| 5 | The source language is gated like any other | The source is just another language on the asset; the review phase already gates it. An `fr`-only editor must not be able to rewrite the Arabic original. |
| 6 | Adding a language auto-assigns it to the creator | Otherwise "add language" leads to an immediate dead end where the creator cannot edit what they just created. |

### Rejected alternatives

- **`role` field or `can_edit`/`can_review` booleans** — expressive enough to let someone edit
  Arabic but review French. No demand for that; the cost is a doubled assignment UI and a role
  filter on every authorization query. Revisit only if a concrete case appears.
- **Empty assignments meaning "all languages"** — needs no migration, but contradicts the reviewer
  rule (empty = nothing) and silently un-gates anyone whose assignments are later cleared.
- **Granting the bypass to groups holding `PORTAL_REVIEW_CONTENT`** — would un-gate reviewers who
  are deliberately restricted today. The rollout must preserve behaviour, not widen it.

## Architecture

### Model

`ReviewerLanguage` is renamed to `MemberLanguage`; nothing else about it changes.

```python
class MemberLanguage(BaseModel):                                  # apps/publishers/models.py
    member = FK(PublisherMember, on_delete=CASCADE, related_name="languages")
    language = CharField(max_length=10)

    class Meta:
        constraints = [UniqueConstraint(fields=["member", "language"],
                                        name="unique_member_language")]
```

Semantics, unchanged in spirit and now role-neutral: **a member with no rows works in no
languages.** The bypass permission, not an empty list, is how someone gets access to everything.

Because the creating migrations (`content.0061`, `publishers.0014`) are unshipped and the tables
are empty, this is a plain rename — no data migration, no `SeparateDatabaseAndState`.

### Authorization: one rule, two layers

The bypass needs the asset (to enumerate its languages); the assignment lookup does not. Splitting
them keeps the `content → publishers` dependency direction established earlier in this branch —
`publishers` must not import `content`.

```python
# apps/publishers/services/membership.py  — no content imports
def member_languages(user, publisher_id) -> set[str]:
    """Languages assigned to this user's ACTIVE membership in this publisher."""

# apps/content/services/asset_language_access.py  — applies the bypass
def allowed_languages(user, asset) -> set[str]:
    if check_permission(user, PermissionChoice.PORTAL_ACCESS_ALL_LANGUAGES):
        return {every language on asset, including the source}
    return member_languages(user, asset.publisher_id)

def require_language(user, asset, language) -> None:
    """Raise ItqanError(language_not_assigned, 403) unless language is allowed."""
```

`AssetReviewService.assigned_languages` is deleted and its callers re-pointed at
`allowed_languages`. Review and editing then share one implementation and cannot drift apart.

### Permissions

```python
PORTAL_ACCESS_ALL_LANGUAGES = "portal_access_all_languages", _("Portal - Access All Languages")
PORTAL_ADD_ASSET_LANGUAGE   = "portal_add_asset_language",   _("Portal - Add Asset Language")
```

`Itqan Internal` is seeded with `PermissionChoice.values` (`apps/publishers/apps.py:46`), so it
acquires both automatically. No implication entries are added: the bypass deliberately grants no
edit or review rights of its own.

### Enforcement

Filtering the picker is not sufficient on its own. Two ways a client could route around it, both
of which must be closed:

- **Writes** that name a language directly (`data.language`) — the client is simply not trusted.
- **Version-scoped endpoints**, which take a `version_id` rather than a language. A version id
  resolves to exactly one language, so leaving these open would expose an unassigned language's
  content to anyone who can guess or enumerate an id — the picker filter would be security theatre.
  These are therefore gated on the version's own language, **reads included**.

Every row below resolves a language and calls `require_language` unless noted.

| Route | Resolves language from | Change |
|---|---|---|
| `GET content/{category}/{slug}/languages/` | — | filter result to `allowed_languages(user, asset)` |
| `POST content/{category}/{slug}/languages/` | `data.language` | gate on `PORTAL_ADD_ASSET_LANGUAGE` instead of `write=True`; auto-assign the new language to the creator's membership |
| `PATCH content/{category}/{slug}/languages/{language}/availability/` | path param | `require_language` |
| `POST content/{category}/{slug}/draft/` | `data.language` | `require_language` |
| `GET .../versions/{version_id}/entries/` | version | `require_language` |
| `PATCH .../versions/{version_id}/entries/` | version | `require_language` |
| `GET .../versions/{version_id}/diff/` | version | `require_language` |
| `GET .../versions/{version_id}/pending-diff/` | version | `require_language` |
| `GET .../versions/{version_id}/export/` | version | `require_language` |
| `POST .../versions/{version_id}/publish/` | version | `require_language` |
| `POST .../versions/{version_id}/restore/` | version | `require_language` |
| `DELETE .../versions/{version_id}/` | version | `require_language` |
| `GET translations\|tafsirs/{slug}/versions/` | `language` query, else all | `require_language` when filtered; otherwise narrow the queryset to allowed languages |
| `POST translations\|tafsirs/{slug}/versions/` | `data.language`, else source | `require_language` (the field is optional; omitting it targets the source) |
| `PUT/PATCH/DELETE translations\|tafsirs/{slug}/versions/{version_id}/` | version | `require_version_id` — six routes, two per category |
| review endpoints (`review/languages/`, `review/changes/`, PATCH) | existing | behaviour unchanged; now call the shared helper |

Implementation note: the per-category version modules carry PUT, PATCH and DELETE
routes that this table originally missed, taking the true count from 13 to 23.
The list above is the maintained inventory.

Resolving a version's language must handle **legacy versions with no `asset_language`**, which
belong to the asset's source language — the same rule `tafsir_versions.py:113-115` already applies
when filtering. The existing `change_language(change)` in `repositories/asset_review.py:8` already
implements this fallback one level down.

Implemented as `AssetVersion.resolved_language` — a model property rather than a free function in
the access service, so both services and repositories can use it without an off-layer import.
`change_language` now delegates to it, giving the fallback exactly one definition instead of three.

Error contract: `403 language_not_assigned`, reusing the code the review phase already returns.

### API surface rename

The portal member API renames alongside the model (all unshipped):

- `MemberOut.reviewer_languages` → `MemberOut.languages`
- `PUT /portal/members/{id}/reviewer-languages/` → `PUT /portal/members/{id}/languages/`

### Rollout migration

A data migration in `publishers`, after the permission codenames are synced:

```python
edit_codenames = ["portal_update_translation", "portal_update_tafsir"]
groups = Group.objects.filter(permissions__codename__in=edit_codenames).distinct()
for group in groups:
    group.permissions.add(access_all_languages_permission)
```

Reversible by removing the permission from the same set. Groups holding only
`PORTAL_REVIEW_CONTENT` are deliberately untouched (see Rejected alternatives).

### Frontend

- **Add-language button** (`asset-content-grid.component.html:25`) rendered only when
  `hasPermission(PORTAL_ADD_ASSET_LANGUAGE)`.
- **Language picker** needs no change — it renders whatever the API returns, which is now filtered.
- **Member screen** renames `reviewer_languages` → `languages` and relabels the column, modal, and
  tooltip from "Review languages" to "Assigned languages" (en + ar, parity enforced by
  `scripts/check-arabic-translations.js`).

## Testing

- `member_languages` / `allowed_languages`: assigned set; bypass returns all asset languages
  including the source; assignment in another publisher does not leak (the multi-publisher case the
  per-membership refactor exists to prevent).
- Each enforcement point: allowed language succeeds; unassigned language returns
  `403 language_not_assigned` with the asserted `error_name`; bypass holder succeeds on all.
- Version-scoped **reads** specifically: an `fr`-only editor handed the `version_id` of an `es`
  version is refused on `entries/`, `diff/`, and `export/` — the picker filter is not the only gate.
- `version_language()` on a legacy version (no `asset_language`) resolves to the asset's source
  language, so such versions are gated as source rather than silently allowed.
- Source language specifically: `fr`-only editor is refused on the source.
- `POST .../languages/` requires `PORTAL_ADD_ASSET_LANGUAGE` and auto-assigns the creator.
- Rollout migration: a group with `portal_update_translation` gains the bypass; a group with only
  `portal_review_content` does not.
- Review endpoints keep their existing behaviour through the shared helper (regression).

## Out of scope

- Per-role assignment (`role` field / `can_edit` / `can_review`) — see Rejected alternatives.
- Assignment management anywhere other than Django admin and the portal member screen.
- Any change to what review states mean or how they are recorded.

## Risks

- **Source-language gating is the most user-visible change.** An editor assigned only `fr` can no
  longer edit the Arabic source, including through the versions manager. The rollout migration
  protects *existing* editors; members assigned languages after deploy will feel it. Accepted
  deliberately (Decision 5); worth calling out in release notes.
- **Broad enforcement surface.** The gate touches twenty-three routes, including reads. A missed route
  is a silent authorization hole, which is why each one gets its own test rather than relying on
  the picker filter. If a new version-scoped endpoint is added later and forgets `require_language`,
  nothing will fail loudly — the enforcement list above is the checklist to extend.
- **Version-scoped reads are newly restricted.** Anything outside the portal that fetches entries,
  diffs, or exports by `version_id` on behalf of a member now needs either an assignment or the
  bypass. Internal/public APIs are untouched; only the `/portal/` surface changes.
