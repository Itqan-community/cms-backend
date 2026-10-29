# Publisher-Scoped Permission Groups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each publisher owns its own permission groups (roles), defined by its admins, and a member's permissions at a publisher come only from their group at that publisher.

**Architecture:** Keep Django `auth.Group` as the permission container (PublisherMember.group, PermissionHierarchyService and the Django admin already use it) and add a `PublisherGroup` extension row that ties a Group to one publisher and holds its display name. Authorization stops relying on `user.groups` for publisher roles: `check_permission` resolves permissions as *global perms* (user_permissions + non-publisher groups such as Itqan Internal) plus *the active membership's group at the request's publisher*. The portal learns per-publisher permissions from `GET /portal/publishers/me/`.

**Tech Stack:** Django 5.2, django-ninja, plain_permissions, PostgreSQL; Angular (cms-frontend).

**Spec:** No separate spec. The decisions below were derived in the 2026-10-28 session (follow-up to `fix/stop-seeding-publisher-groups`, which removed the hardcoded `Publisher Member` / `Publisher Member Admin` seeding). They are the spec.

## Design Decisions

1. **Ownership.** A publisher group is an `auth.Group` with a `PublisherGroup` row (`publisher`, `name`). Groups without one are *global* (Itqan Internal, staff-only groups) and are never listed or assignable through the portal.
2. **Names.** `auth.Group.name` is globally unique, so a publisher group's `Group.name` is opaque (`f"publisher:{publisher_id}:{uuid4().hex}"`) and never shown. The display name lives on `PublisherGroup.name`, unique per publisher. Renaming touches only `PublisherGroup.name`.
3. **Effective permissions** for `(user, publisher)`:
   - inactive / anonymous → none; active superuser → every `PermissionChoice`;
   - otherwise `global ∪ group_perms(active membership at publisher)`;
   - `publisher is None` (no `X-Tenant`) → `global`, plus `portal_access` if the user has any ACTIVE membership. This is fail-closed: omitting `X-Tenant` must never yield the union of all the user's publishers' roles.
4. **No `user.groups` sync** for publisher groups. Membership activation/removal/group change no longer touches `user.groups`; the membership row is the source of truth.
5. **Bootstrap.** A new publisher has no groups. Itqan staff (Itqan Internal, which is global) create the first admin group for it through the portal with `X-Tenant`. Nothing is seeded or hardcoded.
6. **Grant ceiling.** A non-superuser, non-staff editor may only put permissions into a group that they themselves hold at that publisher (after hierarchy expansion). Staff/superusers are unrestricted.
7. **Existing data.** A migration gives every publisher its own copy (same display name, same permissions) of each group its memberships use, repoints those memberships, and removes publisher-role groups from users' `user.groups`. The original shared Group rows are left in the database untouched ("leave them be"), just no longer assignable.
8. **Frontend compatibility.** `GET /profile` `permissions` keeps today's meaning (global ∪ all ACTIVE memberships' groups) so a frontend that has not switched yet still shows the same buttons. The portal switches to the per-publisher `permissions` on `publishers/me`. The server enforces per-publisher regardless.

## Global Constraints

- Backend tests subclass `apps.core.tests.base.BaseTestCase`, never raw `django.test.TestCase`.
- User-facing errors use `ItqanError` with a `gettext_lazy` message; every new string gets an Arabic `msgstr` (`makemessages`, fill `locale/ar/LC_MESSAGES/django.po`, `msgfmt --check --statistics` reports 0 untranslated, `compilemessages`).
- Document new `error_name`s in the endpoint's `response=` with `NinjaErrorResponse[Literal[...]]`.
- Backend commits are done by the user (repo rule); each "Commit" step means: stop, show the diff, suggested message given.
- Revert `uv.lock` after every `uv run`. Run pre-commit one file at a time.
- Tasks 1–9 (backend) ship as **one PR / one deploy**: the migration in Task 2 removes publisher groups from `user.groups`, which is only safe once Task 3's resolution is live.
- Full backend suite must pass with `--create-db` (the reused test DB still holds rows seeded by the old code).
- Frontend: run `npx prettier --check .`, `ng build`, `ng test`, and `tsc -p tsconfig.app.json --noEmit`.

## Review Focus

1. **Omitted `X-Tenant`.** A user who is an admin at A and a plain member at B calls a B-scoped write endpoint with no `X-Tenant` → denied (403), not granted via A's group. Pinned in Task 3.
2. **Wrong tenant on content checks.** A user who has `portal_review_content` only at A reviews an asset of B with `X-Tenant: B` → 403. Pinned in Task 4.
3. **Privilege escalation through group editing.** A publisher admin holding `portal_update_group` adds `portal_create_publisher` (which they lack) to their own group → 400 `permission_not_grantable`. Pinned in Task 6.
4. **Cross-publisher group ids.** An admin at A invites a member or moves a member into a group id belonging to B → 400 `invalid_group`, and `GET/PUT/DELETE groups/{B's id}/` from A → 404 `group_not_found`. Pinned in Tasks 6 and 7.
5. **Deleting a group still in use.** `DELETE groups/{id}/` while a membership references it → 400 `group_in_use` (today this raises an unhandled `ProtectedError`, a 500). Pinned in Task 6.

---

### Task 1: `PublisherGroup` model

**Files:**
- Modify: `apps/publishers/models.py` (new model after `Publisher`; `PublisherMember.group` `help_text` no longer says "Applied to the user's groups")
- Create: `apps/publishers/migrations/00XX_publishergroup.py` (via `makemigrations`; see the `local-db-migration-history-drift` note: use a fresh `DB_NAME` if history is inconsistent)
- Modify: `apps/publishers/signals.py` (post_delete handler)
- Modify: `apps/publishers/admin.py` (register `PublisherGroup`, list `publisher`, `name`, `group`)
- Test: `apps/publishers/tests/test_publisher_group_model.py`

**Interfaces:**
- Produces: `PublisherGroup(group: OneToOneField("auth.Group", primary_key=True, on_delete=CASCADE, related_name="publisher_group"), publisher: ForeignKey(Publisher, on_delete=CASCADE, related_name="groups"), name: CharField(max_length=150))`, constraint `UniqueConstraint(fields=["publisher", "name"], name="unique_publisher_group_name")`.
- Produces: `PublisherMember.group_display_name -> str` property: `self.group.publisher_group.name` if present, else `self.group.name`.

- [ ] **Step 1: Write failing tests**
  - `test_same_name_allowed_in_two_publishers`: two `PublisherGroup(name="Editors")` for publishers A and B save fine.
  - `test_duplicate_name_in_one_publisher_rejected`: second `"Editors"` for A raises `IntegrityError`.
  - `test_deleting_publisher_group_row_deletes_auth_group`: deleting the `PublisherGroup` leaves no `Group` with that pk.
  - `test_group_display_name_prefers_publisher_group_name`: member whose group has `PublisherGroup(name="Editors")` → `"Editors"`; member on a plain Group named `"Legacy"` → `"Legacy"`.
- [ ] **Step 2: Run, expect FAIL** — `uv run pytest apps/publishers/tests/test_publisher_group_model.py -q` → `ImportError: PublisherGroup`.
- [ ] **Step 3: Implement** the model, migration, `post_delete` receiver on `PublisherGroup` that deletes `instance.group` (so publisher deletion does not orphan `auth.Group` rows), the property, and admin registration.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(publishers): add PublisherGroup to scope permission groups to a publisher`

### Task 2: Data migration — per-publisher copies of existing groups

**Files:**
- Create: `apps/publishers/migrations/00XX_copy_groups_per_publisher.py`
- Test: `apps/publishers/tests/test_copy_groups_per_publisher_migration.py` (call the migration's forward function directly with `django.apps.apps`)

**Interfaces:**
- Consumes: `PublisherGroup` (Task 1).
- Produces: forward function `copy_groups_per_publisher(apps, schema_editor) -> None`; reverse is `migrations.RunPython.noop` (documented in the migration docstring: repointed memberships are not restored).

Algorithm (not determined by the tests alone):
```
internal = Group named "Itqan Internal"
for (publisher_id, group_id) in distinct PublisherMember (any status) pairs
        where group has no PublisherGroup and group != internal:
    new = Group.create(name=f"publisher:{publisher_id}:{uuid4().hex}")
    new.permissions.set(old.permissions.all())
    PublisherGroup.create(group=new, publisher_id=publisher_id, name=old.name)
    PublisherMember.filter(publisher_id, group_id=old).update(group=new)
then for every user with any membership:
    user.groups.remove(*[groups that are publisher-role groups, i.e. any group
                        referenced by a membership before the repoint, or having a PublisherGroup])
```
Itqan Internal membership in `user.groups` must survive.

- [ ] **Step 1: Write failing tests**
  - `test_shared_group_is_copied_per_publisher`: shared Group `"Admin"` with perms `{portal_access, portal_invite_publisher_members}` used by members of A and B → after migration A and B each have a `PublisherGroup(name="Admin")` with exactly those perms, on different Group ids, and each member points at their own publisher's copy.
  - `test_original_group_row_is_left_untouched`: the shared `"Admin"` Group still exists with its original perms.
  - `test_publisher_role_groups_removed_from_user_groups_but_internal_kept`: user in `"Admin"` and `Itqan Internal` → afterwards `user.groups` contains only `Itqan Internal`.
  - `test_migration_is_idempotent`: running the forward function twice creates no extra groups.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the migration.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(publishers): give each publisher its own copy of the groups its members use`

### Task 3: Publisher-scoped permission resolution

**Files:**
- Create: `apps/publishers/services/effective_permissions.py`
- Modify: `apps/core/permission_utils.py` (`permission_class`, `check_permission`)
- Test: `apps/publishers/tests/services/test_effective_permissions.py`, `apps/core/tests/test_permission_utils.py` (extend if it exists)

**Interfaces:**
- Produces: `effective_permissions(user: User, publisher: Publisher | int | None) -> frozenset[str]` (codenames), cached per user instance in `user._effective_perm_cache: dict[int | None, frozenset[str]]`.
- Produces: `effective_permissions_by_publisher(user: User, publisher_ids: Iterable[int]) -> dict[int, frozenset[str]]` — same rule, a fixed number of queries regardless of how many ids (memberships with `select_related("group")` + one `Permission` query over those groups); fills the same cache.
- Changes: `check_permission(user, permission, raise_exception: bool = False, *, publisher: Publisher | int | None = None) -> bool` now returns `permission in effective_permissions(user, publisher)`. `permission_class(...).has_permission` passes `publisher=getattr(request, "publisher", None)`.
- Global perms = codenames of the plain_permissions content type from `user.user_permissions` and from `user.groups` **excluding** groups that have a `PublisherGroup`.

- [ ] **Step 1: Write failing tests**
  - `test_member_gets_only_their_group_at_that_publisher`: admin group at A (`portal_invite_publisher_members`), read group at B → `effective_permissions(user, B)` lacks `portal_invite_publisher_members`; at A it has it.
  - `test_no_publisher_gives_global_plus_portal_access_only`: same user, `publisher=None` → exactly `{"portal_access"}`.
  - `test_pending_membership_grants_nothing`: PENDING membership at A → `effective_permissions(user, A) == frozenset()`.
  - `test_itqan_internal_applies_at_every_publisher`: staff in Itqan Internal, no memberships → full `PermissionChoice.values` at A and at `None`.
  - `test_superuser_has_everything`.
  - `test_by_publisher_query_count_is_constant`: user with 1 vs 5 memberships → `assertNumQueries(N)` with the same N.
  - `test_permission_class_denies_without_tenant` (API level): user's group at A has `portal_delete_publisher_members`, their group at B does not; `DELETE /portal/members/{id of another member at B}/` with no `X-Tenant` → 403 and the member still exists. (Review Focus 1.)
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the module and the `permission_utils` changes (lazy-import the publishers service inside `check_permission` to keep `apps.core` import-light).
- [ ] **Step 4: Run** these tests → PASS; then the full suite with `--create-db`. Failures here are expected in tests that build memberships without per-publisher groups; they are fixed in Tasks 5–7. Note them, do not weaken the rule.
- [ ] **Step 5: Commit** — `feat(auth): resolve portal permissions per publisher membership`

### Task 4: Pass the publisher at direct `check_permission` call sites

**Files:**
- Modify (add `publisher=request.publisher`): `apps/package_manager/api/portal/package_versions.py:50,86`, `apps/content/api/portal/tafsir_versions.py:215,273,323`, `translation_versions.py:227,287,341`, `mushaf_versions.py:135`, `font_versions.py:135`, `asset_columns.py:74,75`, `asset_content.py:98`, `asset_review.py:108`
- Modify: `apps/content/services/asset_language_access.py:56` — `publisher=asset.publisher_id`
- Test: `apps/content/tests/portal/test_publisher_scoped_content_permissions.py`

**Interfaces:**
- Consumes: `check_permission(..., *, publisher=...)` (Task 3).

- [ ] **Step 1: Write failing tests**
  - `test_review_denied_when_permission_held_only_at_other_publisher`: `portal_review_content` only at A; review an asset of B with `X-Tenant: B` → 403. (Review Focus 2.)
  - `test_all_languages_access_is_per_publisher`: `portal_access_all_languages` at A only → `allowed_languages(user, asset_of_B)` is restricted to assigned languages.
- [ ] **Step 2: Run, expect FAIL** (the call sites pass no publisher, so the check uses global perms only — confirm the failure is the expected one, not a fixture error).
- [ ] **Step 3: Implement.** Then `grep -rn "check_permission(" apps --include='*.py' | grep -v tests | grep -v "publisher="` must print only the definition and `permission_class`.
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `fix(auth): scope inline permission checks to the request's publisher`

### Task 5: Stop syncing publisher groups into `user.groups`

**Files:**
- Modify: `apps/publishers/services/publisher_member_service.py` (`grant_member_perms`, `revoke_member_perms`, `update_member`, delete `_groups_from_other_memberships`)
- Modify: `apps/publishers/repositories/publisher_member.py` (delete `other_active_membership_group_ids`)
- Modify: `apps/publishers/services/publisher_member_invitation_service.py:169` (drop the `grant_member_perms` call or keep it as a no-op-free removal)
- Test: `apps/publishers/tests/services/test_publisher_member_service.py`, `test_publisher_member_invitation_service.py`, `apps/publishers/tests/portal/members/*.py`

**Interfaces:**
- Removes: `PublisherMemberService.grant_member_perms`, `revoke_member_perms`, `PublisherMemberRepository.other_active_membership_group_ids`.

- [ ] **Step 1: Rewrite the assertions** that check `user.groups.filter(name=...)` / `user.has_perm(...)` after accept / group change / delete to assert on `effective_permissions(user, publisher)` instead, and add `test_accepting_invite_does_not_touch_user_groups` (`user.groups` unchanged after accept).
- [ ] **Step 2: Run, expect FAIL** on the new test.
- [ ] **Step 3: Implement** the removals.
- [ ] **Step 4: Run** `uv run pytest apps/publishers -q` → PASS.
- [ ] **Step 5: Commit** — `refactor(publishers): derive member permissions from the membership, not user.groups`

### Task 6: Groups API scoped to the request's publisher

**Files:**
- Modify: `apps/users/repositories/group.py`, `apps/users/services/group.py`, `apps/users/api/portal/groups.py`
- Modify: the Django admin group form that calls `GroupService.validate_name` (keeps global-group semantics with `publisher=None`)
- Modify: `apps/publishers/tests/group_helpers.py` — `member_group(*perms, publisher)` / `admin_group(*perms, publisher)` now create a `PublisherGroup` for that publisher
- Test: `apps/users/tests/portal/test_groups_publisher_scope.py` (plus updates to existing groups API tests)

**Interfaces:**
- Consumes: `PublisherGroup` (Task 1), `effective_permissions` (Task 3).
- Produces (service, all take the publisher id explicitly):
  - `GroupService.assignable_groups_qs(publisher_id: int) -> QuerySet[Group]` — `Group.objects.filter(publisher_group__publisher_id=publisher_id).select_related("publisher_group")`
  - `GroupService.resolve_assignable_group(group_id: int, publisher_id: int) -> Group` — same `invalid_group` 400 for missing, other-publisher, and global groups
  - `GroupService.create(publisher_id: int, name: str) -> Group`, `rename(group_id, publisher_id, name)`, `set_permissions(group_id, publisher_id, permissions, *, editor: User)`, `delete(group_id, publisher_id)`
  - `validate_name(name, *, exclude_id=None, publisher_id: int | None = None)` — uniqueness per publisher, or among global groups when `None`
- API: every `groups/` endpoint requires `request.publisher`; `None` → 400 `tenant_required` ("Select a publisher first."). `GroupListOut.name` / `GroupDetailOut.name` resolve from `publisher_group.name`. Other publishers' ids → 404 `group_not_found`.
- New errors: `permission_not_grantable` (400, message lists the codenames), `group_in_use` (400, "This group is assigned to members and cannot be deleted."), `tenant_required` (400).

- [ ] **Step 1: Write failing tests**
  - `test_list_returns_only_this_publishers_groups`
  - `test_same_name_can_exist_in_two_publishers` (create `"Editors"` under A and B → both 201) and `test_duplicate_name_within_publisher_is_400` (`group_already_exists`)
  - `test_other_publishers_group_is_404` for GET / PUT / PUT permissions / DELETE (Review Focus 4)
  - `test_missing_tenant_is_400_tenant_required`
  - `test_editor_cannot_grant_permission_they_lack` → 400 `permission_not_grantable` (Review Focus 3); `test_staff_can_grant_any_permission`
  - `test_delete_group_in_use_is_400_group_in_use` (Review Focus 5)
  - `test_created_group_has_opaque_auth_name`: `Group.name` starts with `f"publisher:{A.id}:"`, response `name == "Editors"`
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** Catch `ProtectedError` in `GroupService.delete` → `group_in_use`. Grant ceiling: `set(hierarchy.with_implied(choices)) - effective_permissions(editor, publisher_id)` must be empty unless the editor is staff/superuser. Add translations.
- [ ] **Step 4: Run** `uv run pytest apps/users apps/publishers -q` → PASS.
- [ ] **Step 5: Commit** — `feat(groups): scope portal groups to the request's publisher`

### Task 7: Member assignment uses the publisher's groups

**Files:**
- Modify: `apps/publishers/services/publisher_member_invitation_service.py:48`, `apps/publishers/services/publisher_member_service.py` (`update_member`) — pass `member.publisher_id` / the invite's publisher to `resolve_assignable_group`
- Modify: `apps/publishers/api/portal/publisher_members.py:58` and the schema at `:249`, `apps/publishers/models.py:185` (`PublisherMemberInvitation.group_name`), `apps/publishers/admin.py:154` — use `group_display_name`; add `select_related("group__publisher_group")` where members are listed
- Test: `apps/publishers/tests/portal/members/test_member_group_scope.py`

**Interfaces:**
- Consumes: `resolve_assignable_group(group_id, publisher_id)` (Task 6), `PublisherMember.group_display_name` (Task 1).

- [ ] **Step 1: Write failing tests**
  - `test_invite_with_other_publishers_group_is_400_invalid_group` and `test_move_member_to_other_publishers_group_is_400_invalid_group` (Review Focus 4)
  - `test_member_list_shows_display_name`: list shows `"Editors"`, not the opaque name
  - `test_member_list_query_count_does_not_grow_with_members`: 2 vs 6 members → same `assertNumQueries`
  - `test_invitation_email_uses_display_name`: rendered invite email context `group_name == "Editors"`
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite with `--create-db` → all PASS (this is the first task where the whole suite must be green again).
- [ ] **Step 5: Commit** — `feat(members): assign only the publisher's own groups and show their display names`

### Task 8: Expose per-publisher permissions to the portal

**Files:**
- Modify: `apps/publishers/api/portal/publishers.py:93-104` (`MyPublisherOut`, `list_my_publishers`)
- Modify: `apps/users/api/internal/profile.py:41` (`_get_user_permissions` keeps union semantics, docstring says deprecated for portal gating)
- Test: `apps/publishers/tests/portal/test_my_publishers_permissions.py`, profile tests

**Interfaces:**
- Consumes: `effective_permissions_by_publisher` (Task 3).
- Produces: `MyPublisherOut.permissions: list[str]` (sorted codenames, effective at that publisher).

- [ ] **Step 1: Write failing tests**
  - `test_each_publisher_lists_its_own_permissions`: admin at A, reader at B → A's entry contains `portal_invite_publisher_members`, B's does not
  - `test_my_publishers_query_count_constant`: 1 vs 5 memberships → same query count
  - `test_profile_permissions_still_union_of_memberships`: profile lists `portal_invite_publisher_members` for the same user (compat, Decision 8)
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.** The profile union = global ∪ all ACTIVE memberships' group perms (no longer derivable from `user.get_all_permissions()` after Task 5).
- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `feat(publishers): return each publisher's effective permissions from publishers/me`

### Task 9: Backend docs and pre-deploy check

**Files:**
- Modify: `docs/ARCHITECTURE.md` (publisher section ~lines 213–219 and the ER diagram: `PublisherGroup`, per-publisher resolution, fail-closed no-tenant rule, grant ceiling, bootstrap by staff)
- Modify: `locale/ar/LC_MESSAGES/django.po`

- [ ] **Step 1:** Update the docs; run the localization gate (0 untranslated, compiles).
- [ ] **Step 2:** Give the user a read-only prod command (Claude cannot SSH to prod) that counts what the Task 2 migration will create: distinct `(publisher_id, group_id)` pairs in `PublisherMember` excluding Itqan Internal, and users whose `groups` contain a membership group. Record the numbers in the PR description.
- [ ] **Step 3: Commit** — `docs: describe publisher-scoped permission groups`

### Task 10 (cms-frontend): Gate the portal on the selected publisher's permissions

Follow `cms-frontend/AGENTS.md` and `cms-frontend/.claude/` first.

**Files:**
- Modify: `src/app/features/admin/services/admin-tenant.service.ts` (`MyPublisherOut` gains `permissions: string[]`; add `refresh(): Observable<void>` that reloads `publishers/me` and keeps the selection)
- Modify: `src/app/features/admin/services/admin-auth.service.ts:13` (`permissionCodes` = selected publisher's `permissions` when a valid tenant is selected, else profile `permissions`)
- Modify: the group-permissions save handler under `src/app/features/admin/members/` (call `adminTenant.refresh()` after a successful save so editing your own group updates buttons without reload)
- Test: the matching `*.spec.ts` files

**Interfaces:**
- Consumes: `GET /portal/publishers/me/` → `[{id, name, slug, icon_url, permissions: string[]}]` (Task 8).

- [ ] **Step 1: Write failing specs**
  - `permissionCodes reflects the selected publisher`: publishers A `[portal_invite_publisher_members]`, B `[]`; select B → `hasPermission('portal_invite_publisher_members')` false; select A → true
  - `falls back to profile permissions before a tenant is selected`
  - `saving group permissions refreshes publishers/me`
- [ ] **Step 2: Run** `npx ng test --watch=false` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `ng test`, `ng build`, `npx tsc -p tsconfig.app.json --noEmit`, `npx prettier --check .` → all clean.
- [ ] **Step 5: Verify in Chrome** (claude-in-chrome, on a smaller-model subagent): against local backend, a user admin at A and reader at B sees the invite button only while A is selected; renaming a group in A doesn't show up under B.
- [ ] **Step 6: Commit** — `feat(admin): gate portal actions on the selected publisher's permissions`

## Rollout

1. Run Task 9 Step 2 on prod and sanity-check the counts.
2. Deploy the backend PR (Tasks 1–9). The migration runs on deploy. The old frontend keeps working because profile `permissions` keeps its meaning; users in several publishers may briefly see a button that the server now rejects at the wrong tenant (403).
3. Deploy the frontend PR (Task 10).
4. For any publisher with no groups after migration (no members yet), Itqan staff create its first admin group.
