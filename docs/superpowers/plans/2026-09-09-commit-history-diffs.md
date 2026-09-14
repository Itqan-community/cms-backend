# Commit-style History with Diffs & Restore — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn each publish into a git-style commit (required message + stored per-ayah delta), with a per-language history that shows each commit's diff and can download or restore any past commit.

**Architecture:** Approach A — a commit is one published `AssetVersion` (per language); each new commit stores its delta from the predecessor as `AssetVersionChange` rows (the stored diff); only the head keeps full `AssetVersionEntry` + `file_url`; superseded new-era commits are pruned to deltas; download/restore replay deltas. Dual-mode read paths keep pre-feature commits working with no data migration.

**Tech Stack:** Django + Django Ninja (backend); Angular 20 + signals + ng-zorro + ag-grid (frontend).

**Spec:** `docs/superpowers/specs/2026-09-09-commit-history-diffs-design.md`

## Global Constraints

- **Repo rule — the human commits.** Do NOT run `git commit`/`git push`. "Commit" steps are checkpoint markers; leave changes staged/working for the user. Two independent repos (`itqan-cms-backend`, `cms-frontend`) — never one commit across both.
- **Branch:** stack on `feat/text-edit-enhancements` in both repos (user's explicit choice); backend migrations continue after `0057` (i.e. `0058`+).
- **Backend commands from `itqan-cms-backend/`; frontend from `cms-frontend/`.** Python is `.venv/bin/python`. First run after a schema change: `--create-db`; otherwise `--reuse-db`.
- **Backend tests use `BaseTestCase`** (`apps.core.tests.base`) + `model_bakery.baker`; mirror `apps/content/tests/portal/test_asset_content.py`.
- **All user-facing `_()` strings** need `extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header` + an Arabic `.po` entry; FE user-facing text goes through ngx-translate in **both** `en.json` and `ar.json`.
- **Service→Repository for writes; direct-model reads for portal. Errors via `ItqanError`/`NinjaErrorResponse`.**
- **Per-language:** commits/diffs/restore belong to the version's `asset_language`. No cross-language snapshots.
- **Prune rule (critical):** only prune a superseded head that HAS stored change rows. Never prune a commit that has neither entries nor changes (would lose content). Legacy (pre-feature) commits keep their full entries.

---

## File Structure

Backend (`itqan-cms-backend/`):
- `apps/content/models.py` — add `ChangeTypeChoice` + `AssetVersionChange`.
- `apps/content/migrations/0058_assetversionchange.py` — schema (via makemigrations).
- `apps/content/repositories/asset_content.py` — delta compute/record, prune, reconstruct, computed-diff.
- `apps/content/services/asset_content.py` — publish takes required `message`; wires record/prune; diff + reconstruct + pending-diff service methods.
- `apps/content/api/portal/asset_content.py` — `message` on publish; `diff/`, `pending-diff/` endpoints; export + restore use reconstruction.
- `apps/content/api/portal/tafsir_versions.py` + `translation_versions.py` — add `created_by`/`change_counts` to the list output.
- Tests under `apps/content/tests/`.

Frontend (`cms-frontend/`):
- `src/app/features/admin/models/asset-content.models.ts` — diff/change models.
- `src/app/features/admin/services/asset-content.service.ts` — `pendingChanges`, `versionDiff`, `commit(message)`.
- `src/app/features/admin/components/asset-content-grid/*` — commit dialog (required message + change review).
- `src/app/features/admin/components/asset-versions-manager/*` — commit-log rows (message/author/counts) + expandable diff panel.
- `src/app/features/admin/models/asset-versions.models.ts` — `created_by`, `change_counts` on `AssetVersion`.
- i18n `public/i18n/en.json` + `ar.json`.

---

## Task 1: `AssetVersionChange` model + migration

**Files:**
- Modify: `apps/content/models.py` (add after `AssetVersionEntry`)
- Create: `apps/content/migrations/0058_assetversionchange.py` (makemigrations)
- Test: `apps/content/tests/models/test_asset_version_change.py`

**Interfaces:**
- Produces: `ChangeTypeChoice` (`ADDED="added"`, `MODIFIED="modified"`, `REMOVED="removed"`); `AssetVersionChange(version, ayah, change_type, old_text, new_text, order)` with `related_name="changes"`.

- [ ] **Step 1: Write the failing test**

```python
# apps/content/tests/models/test_asset_version_change.py
from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, AssetVersionChange, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura


class AssetVersionChangeModelTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, language="ar")
        self.version = baker.make(AssetVersion, asset=self.asset)
        self.sura = baker.make(Sura, id=1, name="الفاتحة", ayas_count=3)
        self.ayah = baker.make(Ayah, id=1, sura=self.sura, number_in_sura=1, text="ayah 1")

    def test_unique_change_per_version_ayah(self):
        AssetVersionChange.objects.create(
            version=self.version, ayah=self.ayah, change_type="modified", old_text="a", new_text="b", order=1
        )
        with self.assertRaises(IntegrityError):
            AssetVersionChange.objects.create(
                version=self.version, ayah=self.ayah, change_type="added", old_text="", new_text="c", order=1
            )

    def test_related_name_changes(self):
        AssetVersionChange.objects.create(
            version=self.version, ayah=self.ayah, change_type="added", old_text="", new_text="x", order=1
        )
        self.assertEqual(1, self.version.changes.count())
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_version_change.py --create-db -q`
Expected: FAIL (`cannot import name 'AssetVersionChange'`).

- [ ] **Step 3: Add the model**

```python
# apps/content/models.py — after AssetVersionEntry
class ChangeTypeChoice(models.TextChoices):
    ADDED = "added", _("Added")
    MODIFIED = "modified", _("Modified")
    REMOVED = "removed", _("Removed")


class AssetVersionChange(BaseModel):
    """One changed ayah in a commit — the stored per-ayah diff vs the predecessor."""

    version = models.ForeignKey(AssetVersion, on_delete=models.CASCADE, related_name="changes")
    ayah = models.ForeignKey("quran.Ayah", on_delete=models.PROTECT, related_name="+")
    change_type = models.CharField(max_length=10, choices=ChangeTypeChoice)
    old_text = models.TextField(blank=True, help_text="Previous text; empty for added")
    new_text = models.TextField(blank=True, help_text="New text; empty for removed")
    order = models.PositiveIntegerField(default=0, help_text="Ayah index, for display ordering")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["version", "ayah"], name="unique_change_per_version_ayah"),
        ]
        indexes = [models.Index(fields=["version", "order"])]

    def __str__(self):
        return f"AssetVersionChange(version_id={self.version_id}, ayah_id={self.ayah_id}, {self.change_type})"
```

- [ ] **Step 4: Make + apply migration**

Run:
```bash
.venv/bin/python manage.py makemigrations content --name assetversionchange
.venv/bin/python manage.py migrate content
```
Expected: creates `0058_assetversionchange.py`; applies cleanly.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_version_change.py --create-db -q`
Expected: PASS (2).

- [ ] **Step 6: Commit (staged for user)**

```bash
git add apps/content/models.py apps/content/migrations/0058_*.py apps/content/tests/models/test_asset_version_change.py
# user commits: feat(content): add AssetVersionChange (per-commit delta)
```

---

## Task 2: Record deltas + prune on publish; require commit message

**Files:**
- Modify: `apps/content/repositories/asset_content.py` (`publish_draft`, new `_record_changes`, `prune_version_snapshot`)
- Modify: `apps/content/services/asset_content.py` (`publish_draft` requires `message`)
- Modify: `apps/content/api/portal/asset_content.py` (`PublishIn.message`; 400 mapping)
- Test: `apps/content/tests/portal/test_asset_content.py`

**Interfaces:**
- Consumes: `AssetVersionChange`, `ChangeTypeChoice` (Task 1).
- Produces:
  - `AssetContentRepository._record_changes(new_version, previous_head) -> dict[str, int]` (keys `added`/`modified`/`removed`)
  - `AssetContentRepository.prune_version_snapshot(version) -> None`
  - `AssetContentService.publish_draft(slug, category, version_id, *, message, publisher_q=None) -> AssetVersion` (message required)

- [ ] **Step 1: Write the failing tests**

```python
# in test_asset_content.py (PublishDraftTest or a new CommitTest class)
def test_commit_records_delta_and_prunes_previous_head(self):
    self.authenticate_user(self.user)
    self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
    ar = self.translation.get_or_create_source_language()
    head = baker.make(AssetVersion, asset=self.translation, asset_language=ar,
                      name="v1", state=VersionStateChoice.PUBLISHED)
    baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="old one", order=1)
    baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[1], text="two", order=2)
    # record a stored delta on head so the prune rule allows pruning it
    baker.make("content.AssetVersionChange", version=head, ayah=self.ayahs[0],
               change_type="added", new_text="old one", order=1)
    # a draft that modifies ayah 1 and adds ayah 3, leaves ayah 2
    draft = baker.make(AssetVersion, asset=self.translation, asset_language=ar,
                       name="v2", state=VersionStateChoice.DRAFT, content_edited=True)
    baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="new one", order=1)
    baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[1], text="two", order=2)
    baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[2], text="three", order=3)

    response = self.client.post(
        f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
        data={"message": "tweak ayah 1, add ayah 3"}, content_type="application/json",
    )

    self.assertEqual(200, response.status_code, response.content)
    draft.refresh_from_db()
    self.assertEqual("tweak ayah 1, add ayah 3", draft.summary)
    changes = {c.ayah_id: c.change_type for c in draft.changes.all()}
    self.assertEqual("modified", changes[self.ayahs[0].id])
    self.assertEqual("added", changes[self.ayahs[2].id])
    self.assertNotIn(self.ayahs[1].id, changes)  # unchanged ayah not recorded
    # previous head pruned (it had stored changes)
    self.assertEqual(0, head.entries.count())

def test_commit_requires_message(self):
    self.authenticate_user(self.user)
    self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
    draft = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.DRAFT, content_edited=True)
    baker.make(AssetVersionEntry, version=draft, ayah=self.ayahs[0], text="x")

    response = self.client.post(
        f"/portal/content/translations/{self.translation.slug}/versions/{draft.id}/publish/",
        data={"message": "   "}, content_type="application/json",
    )
    self.assertEqual(400, response.status_code, response.content)
    self.assertEqual("commit_message_required", response.json()["error_name"])
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_content.py -k "commit_records or requires_message" --create-db -q`
Expected: FAIL.

- [ ] **Step 3: Implement repo delta/prune**

```python
# apps/content/repositories/asset_content.py — new methods on AssetContentRepository
def _entries_map(self, version: AssetVersion) -> dict[int, str]:
    return {e.ayah_id: (e.text or "") for e in version.entries.all()}

def _order_map(self, version: AssetVersion) -> dict[int, int]:
    return {e.ayah_id: e.order for e in version.entries.all()}

def _record_changes(self, new_version: AssetVersion, previous_head: AssetVersion | None) -> dict[str, int]:
    """Store AssetVersionChange rows for new_version's delta vs previous_head. Returns counts."""
    from apps.content.models import AssetVersionChange, ChangeTypeChoice

    old = self._entries_map(previous_head) if previous_head is not None else {}
    new = self._entries_map(new_version)
    orders = self._order_map(new_version)
    rows: list[AssetVersionChange] = []
    counts = {"added": 0, "modified": 0, "removed": 0}
    for ayah_id, new_text in new.items():
        if ayah_id not in old:
            ctype = ChangeTypeChoice.ADDED
        elif old[ayah_id] != new_text:
            ctype = ChangeTypeChoice.MODIFIED
        else:
            continue
        rows.append(AssetVersionChange(version=new_version, ayah_id=ayah_id, change_type=ctype,
                                       old_text=old.get(ayah_id, ""), new_text=new_text,
                                       order=orders.get(ayah_id, ayah_id)))
        counts["added" if ctype == ChangeTypeChoice.ADDED else "modified"] += 1
    for ayah_id, old_text in old.items():
        if ayah_id not in new:
            rows.append(AssetVersionChange(version=new_version, ayah_id=ayah_id,
                                           change_type=ChangeTypeChoice.REMOVED,
                                           old_text=old_text, new_text="", order=ayah_id))
            counts["removed"] += 1
    if rows:
        AssetVersionChange.objects.bulk_create(rows, batch_size=1000)
    return counts

def prune_version_snapshot(self, version: AssetVersion) -> None:
    """Drop a superseded commit's full snapshot (entries + file), keeping its deltas."""
    version.entries.all().delete()
    if version.file_url:
        version.file_url.delete(save=False)
        version.save(update_fields=["file_url", "size_bytes", "updated_at"])
```

Then extend `publish_draft` (repo) to record + prune. Insert after the empty-row drop, before flipping state, capture the previous head; after saving, prune:

```python
# in publish_draft, at the top of the method body:
language = draft.asset_language.language if draft.asset_language_id else draft.asset.language
previous_head = draft.asset.get_latest_version(language)  # current published head (not this draft)
draft.entries.filter(text="").delete()
self._record_changes(draft, previous_head)
# ... existing flip-to-published + file generation ...
# ... after draft.save(...) and asset.save(...):
if previous_head is not None and previous_head.changes.exists():
    self.prune_version_snapshot(previous_head)
return draft
```

- [ ] **Step 4: Implement service + endpoint (message required)**

```python
# apps/content/services/asset_content.py — publish_draft
def publish_draft(self, slug, category, version_id, *, message: str, publisher_q=None):
    asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
    draft = self._get_editable_draft_or_400(asset, version_id)
    if not draft.content_edited:
        raise ItqanError(error_name="no_changes_to_publish",
                         message=_("There are no changes to publish."), status_code=400)
    if not (message or "").strip():
        raise ItqanError(error_name="commit_message_required",
                         message=_("A commit message is required."), status_code=400)
    draft.summary = message.strip()
    published = self.repo.publish_draft(draft)
    notify_asset_version_created.delay(published.pk)
    return published
```

```python
# apps/content/api/portal/asset_content.py
class PublishIn(Schema):
    message: str

# publish endpoint response: add commit_message_required
#   400: NinjaErrorResponse[Literal["version_not_editable"]]
#        | NinjaErrorResponse[Literal["no_changes_to_publish"]]
#        | NinjaErrorResponse[Literal["commit_message_required"]]
def publish_draft(request, category, slug, version_id, data: PublishIn):
    resolved = _resolve(category, request, write=True)
    return AssetContentService().publish_draft(
        slug, resolved, version_id, message=data.message, publisher_q=request.publisher_q())
```

Update existing publish tests to send `{"message": "..."}` instead of `{}` / `{name, summary}`.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_content.py --create-db -q`
Expected: PASS (fix any publish tests that sent the old payload).

- [ ] **Step 6: extendedmakemessages + Arabic**

Run: `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header`
Then add to `locale/ar/LC_MESSAGES/django.po`: `"A commit message is required."` → `"رسالة التغيير مطلوبة."` and run `uv run manage.py compilemessages --locale=ar`.

- [ ] **Step 7: Commit (staged for user)**

```bash
git add apps/content/repositories/asset_content.py apps/content/services/asset_content.py apps/content/api/portal/asset_content.py apps/content/tests/ locale/ar/LC_MESSAGES/django.po
# user commits: feat(content): record per-commit deltas, prune superseded heads, require commit message
```

---

## Task 3: Diff API (dual-mode) + author/change-counts on the version list

**Files:**
- Modify: `apps/content/repositories/asset_content.py` (`version_diff` dual-mode)
- Modify: `apps/content/services/asset_content.py` (`get_version_diff`)
- Modify: `apps/content/api/portal/asset_content.py` (`diff/` endpoint, `ChangeOut`)
- Modify: `apps/content/api/portal/tafsir_versions.py` + `translation_versions.py` (`created_by`, `change_counts`)
- Test: `apps/content/tests/portal/test_asset_content.py`, `.../test_tafsirs_versions.py`

**Interfaces:**
- Consumes: Task 2 (`_entries_map`, stored changes).
- Produces:
  - `AssetContentRepository.version_diff(version) -> list[dict]` with keys `ayah_id, sura, aya, surah_name, change_type, old_text, new_text` (stored rows if present; else computed vs predecessor).
  - `diff/` endpoint (paginated) returning `list[ChangeOut]`.
  - Version list rows expose `created_by: str | None`, `change_counts: dict|null`.

- [ ] **Step 1: Write failing tests**

```python
def test_diff_returns_stored_changes(self):
    self.authenticate_user(self.user)
    self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
    v = baker.make(AssetVersion, asset=self.translation, state=VersionStateChoice.PUBLISHED)
    baker.make("content.AssetVersionChange", version=v, ayah=self.ayahs[0],
               change_type="modified", old_text="a", new_text="b", order=1)
    resp = self.client.get(
        f"/portal/content/translations/{self.translation.slug}/versions/{v.id}/diff/")
    self.assertEqual(200, resp.status_code, resp.content)
    row = resp.json()["results"][0]
    self.assertEqual("modified", row["change_type"])
    self.assertEqual("a", row["old_text"])
    self.assertEqual("b", row["new_text"])
    self.assertEqual(1, row["aya"])

def test_diff_computed_for_legacy_commit(self):
    # legacy: no stored changes, full entries on both versions
    self.authenticate_user(self.user)
    self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
    ar = self.translation.get_or_create_source_language()
    from django.utils import timezone
    from datetime import timedelta
    old = baker.make(AssetVersion, asset=self.translation, asset_language=ar,
                     state=VersionStateChoice.PUBLISHED)
    AssetVersion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=1))
    baker.make(AssetVersionEntry, version=old, ayah=self.ayahs[0], text="a")
    new = baker.make(AssetVersion, asset=self.translation, asset_language=ar,
                     state=VersionStateChoice.PUBLISHED)
    baker.make(AssetVersionEntry, version=new, ayah=self.ayahs[0], text="b")
    resp = self.client.get(
        f"/portal/content/translations/{self.translation.slug}/versions/{new.id}/diff/")
    row = resp.json()["results"][0]
    self.assertEqual("modified", row["change_type"])
    self.assertEqual("a", row["old_text"])
    self.assertEqual("b", row["new_text"])
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_content.py -k "diff" --create-db -q`
Expected: FAIL (404 route missing).

- [ ] **Step 3: Implement repo `version_diff`**

```python
def _predecessor(self, version: AssetVersion) -> AssetVersion | None:
    return (self.asset_version_model.objects
            .filter(asset=version.asset, asset_language=version.asset_language,
                    state=VersionStateChoice.PUBLISHED, created_at__lt=version.created_at)
            .exclude(pk=version.pk).order_by("-created_at", "-id").first())

def version_diff(self, version: AssetVersion) -> list[dict]:
    stored = list(version.changes.select_related("ayah", "ayah__sura").order_by("order", "ayah_id"))
    if stored:
        return [self._change_to_dict(c.ayah, c.change_type, c.old_text, c.new_text) for c in stored]
    # legacy: compute vs predecessor from reconstructed snapshots
    from apps.content.models import ChangeTypeChoice
    new = self.reconstruct_entries(version)
    pred = self._predecessor(version)
    old = self.reconstruct_entries(pred) if pred is not None else {}
    ayah_ids = sorted(set(old) | set(new))
    ayah_by_id = {a.id: a for a in Ayah.objects.filter(id__in=ayah_ids).select_related("sura")}
    out = []
    for aid in ayah_ids:
        if aid in new and aid not in old:
            out.append(self._change_to_dict(ayah_by_id[aid], ChangeTypeChoice.ADDED, "", new[aid]))
        elif aid in old and aid not in new:
            out.append(self._change_to_dict(ayah_by_id[aid], ChangeTypeChoice.REMOVED, old[aid], ""))
        elif old.get(aid) != new.get(aid):
            out.append(self._change_to_dict(ayah_by_id[aid], ChangeTypeChoice.MODIFIED, old[aid], new[aid]))
    return out

def _change_to_dict(self, ayah, change_type, old_text, new_text) -> dict:
    return {"ayah_id": ayah.id, "sura": ayah.sura_id, "aya": ayah.number_in_sura,
            "surah_name": ayah.sura.name, "change_type": str(change_type),
            "old_text": old_text, "new_text": new_text}
```

(`reconstruct_entries` is added in Task 4; if implementing Task 3 first, add a temporary `reconstruct_entries` that returns `self._entries_map(version)` — Task 4 replaces it. To avoid ordering coupling, implement Task 4's `reconstruct_entries` here.)

- [ ] **Step 4: Service + endpoint**

```python
# service
def get_version_diff(self, slug, category, version_id, publisher_q=None) -> list[dict]:
    version = self.get_version_or_404(slug, category, version_id, publisher_q=publisher_q)
    return self.repo.version_diff(version)
```

```python
# apps/content/api/portal/asset_content.py
class ChangeOut(Schema):
    ayah_id: int
    sura: int
    aya: int
    surah_name: str
    change_type: str
    old_text: str
    new_text: str

@router.get("content/{category}/{slug}/versions/{version_id}/diff/",
    response={200: list[ChangeOut], 404: NinjaErrorResponse[Literal["version_not_found"]]
              | NinjaErrorResponse[Literal["translation_not_found"]]
              | NinjaErrorResponse[Literal["tafsir_not_found"]]
              | NinjaErrorResponse[Literal["unsupported_content_category"]]})
@paginate
def version_diff(request, category, slug, version_id):
    resolved = _resolve(category, request, write=False)
    return AssetContentService().get_version_diff(slug, resolved, version_id, publisher_q=request.publisher_q())
```

- [ ] **Step 5: Version list — author + counts**

Add to `TafsirVersionListOut` and `TranslationVersionListOut`:
```python
created_by: str | None
change_counts: dict | None

@staticmethod
def resolve_created_by(obj: AssetVersion) -> str | None:
    return obj.created_by.name if obj.created_by_id else None

@staticmethod
def resolve_change_counts(obj: AssetVersion) -> dict | None:
    rows = obj.changes.all()
    if not rows:
        return None
    counts = {"added": 0, "modified": 0, "removed": 0}
    for c in rows:
        counts[c.change_type] = counts.get(c.change_type, 0) + 1
    return counts
```
Prefetch `changes` in the list querysets to avoid N+1: `.prefetch_related("changes")`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/ -k "diff or version" --create-db -q`
Expected: PASS.

- [ ] **Step 7: Commit (staged for user)**

```bash
git add apps/content/repositories/ apps/content/services/ apps/content/api/portal/ apps/content/tests/portal/
# user commits: feat(content): version diff endpoint (dual-mode) + author/change-counts on version list
```

---

## Task 4: Reconstruction + historical download + restore

**Files:**
- Modify: `apps/content/repositories/asset_content.py` (`reconstruct_entries`, adapt `restore_version`, adapt `entries_to_csv_bytes` to accept a map)
- Modify: `apps/content/api/portal/asset_content.py` (export uses reconstruction)
- Test: `apps/content/tests/portal/test_asset_content.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `AssetContentRepository.reconstruct_entries(version) -> dict[int, str]`
  - `restore_version(version, *, created_by_id=None)` works when `version` has no full entries (reconstructs).

- [ ] **Step 1: Write failing tests**

```python
def test_reconstruct_folds_deltas(self):
    ar = self.translation.get_or_create_source_language()
    from django.utils import timezone
    from datetime import timedelta
    # c1 snapshot (has entries) — the anchor
    c1 = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
    AssetVersion.objects.filter(pk=c1.pk).update(created_at=timezone.now() - timedelta(hours=2))
    baker.make(AssetVersionEntry, version=c1, ayah=self.ayahs[0], text="one")
    # c2 delta-only: modify ayah1, add ayah2 (no entries → pruned form)
    c2 = baker.make(AssetVersion, asset=self.translation, asset_language=ar, state=VersionStateChoice.PUBLISHED)
    AssetVersion.objects.filter(pk=c2.pk).update(created_at=timezone.now() - timedelta(hours=1))
    baker.make("content.AssetVersionChange", version=c2, ayah=self.ayahs[0], change_type="modified", old_text="one", new_text="ONE", order=1)
    baker.make("content.AssetVersionChange", version=c2, ayah=self.ayahs[1], change_type="added", new_text="two", order=2)

    from apps.content.repositories.asset_content import AssetContentRepository
    state = AssetContentRepository().reconstruct_entries(c2)
    self.assertEqual({self.ayahs[0].id: "ONE", self.ayahs[1].id: "two"}, state)

def test_restore_reconstructs_pruned_version(self):
    self.authenticate_user(self.user)
    self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
    ar = self.translation.get_or_create_source_language()
    # pruned old commit represented only by deltas
    from django.utils import timezone
    from datetime import timedelta
    old = baker.make(AssetVersion, asset=self.translation, asset_language=ar, name="v1", state=VersionStateChoice.PUBLISHED)
    AssetVersion.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=2))
    baker.make("content.AssetVersionChange", version=old, ayah=self.ayahs[0], change_type="added", new_text="old text", order=1)
    head = baker.make(AssetVersion, asset=self.translation, asset_language=ar, name="v2", state=VersionStateChoice.PUBLISHED)
    baker.make(AssetVersionEntry, version=head, ayah=self.ayahs[0], text="head text")

    resp = self.client.post(
        f"/portal/content/translations/{self.translation.slug}/versions/{old.id}/restore/",
        data={}, content_type="application/json")
    self.assertEqual(200, resp.status_code, resp.content)
    latest = self.translation.get_latest_version("ar")
    self.assertEqual("old text", latest.entries.get(ayah_id=self.ayahs[0].id).text)
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_content.py -k "reconstruct or restore_reconstructs" --create-db -q`
Expected: FAIL.

- [ ] **Step 3: Implement `reconstruct_entries`**

```python
def reconstruct_entries(self, version: AssetVersion) -> dict[int, str]:
    """Full {ayah_id: text} at this commit. Uses entries if present, else folds
    snapshots+deltas up to this commit for its (asset, language)."""
    direct = self._entries_map(version)
    if direct:
        return direct
    from apps.content.models import ChangeTypeChoice
    timeline = (self.asset_version_model.objects
                .filter(asset=version.asset, asset_language=version.asset_language,
                        state=VersionStateChoice.PUBLISHED, created_at__lte=version.created_at)
                .order_by("created_at", "id").prefetch_related("entries", "changes"))
    state: dict[int, str] = {}
    for commit in timeline:
        entry_map = {e.ayah_id: (e.text or "") for e in commit.entries.all()}
        if entry_map:
            state = entry_map
            continue
        for ch in commit.changes.all():
            if ch.change_type == ChangeTypeChoice.REMOVED:
                state.pop(ch.ayah_id, None)
            else:
                state[ch.ayah_id] = ch.new_text
    return state
```

- [ ] **Step 4: Adapt `restore_version` to reconstruct**

Replace the entry-copy in `restore_version` with reconstruction:
```python
snapshot = self.reconstruct_entries(version)  # {ayah_id: text}
# ... create new_version (as today) ...
order_index = self._order_map(version) or {}
copies = [AssetVersionEntry(version=new_version, ayah_id=aid, text=text, order=order_index.get(aid, aid))
          for aid, text in snapshot.items() if text != ""]
if copies:
    AssetVersionEntry.objects.bulk_create(copies, batch_size=1000)
    # record delta vs current head + generate file, then prune the superseded head
    ...
```
Then `restore_version` must ALSO record changes (delta vs the current head at restore time) and prune, so restored commits behave like any other commit. Reuse `_record_changes` + `prune_version_snapshot` exactly as `publish_draft` does.

- [ ] **Step 5: Historical download via reconstruction**

In the export endpoint (`export_version`), when `not version.entries.exists()`, reconstruct and serialize:
```python
if not version.entries.exists():
    snapshot = service.repo.reconstruct_entries(version)
    if not snapshot and not version.file_url:
        raise ItqanError(error_name="version_not_found", message="This version has no downloadable content.", status_code=404)
    content = service.repo.snapshot_to_csv_bytes(version, snapshot, verbose=True)
    ...  # same Content-Disposition filename logic
```
Add `snapshot_to_csv_bytes(version, snapshot, *, verbose)` — same columns as `entries_to_csv_bytes` but iterating a reconstructed `{ayah_id: text}` (join `Ayah` for sura/aya/name/uthmani).

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_content.py -k "reconstruct or restore or export" --create-db -q`
Expected: PASS.

- [ ] **Step 7: Full backend gate + commit (staged)**

Run:
```bash
.venv/bin/python -m pytest apps/content/ --create-db -q
.venv/bin/ruff check apps/content/
.venv/bin/python manage.py makemigrations --check --dry-run
```
```bash
git add apps/content/
# user commits: feat(content): delta reconstruction, historical download, delta-aware restore
```

---

## Task 5: Frontend — commit dialog (required message + change review)

**Files:**
- Modify: `src/app/features/admin/models/asset-content.models.ts` (`ContentChange`, `PendingChanges`)
- Modify: `src/app/features/admin/services/asset-content.service.ts` (`pendingChanges`, `commit`)
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.{ts,html,less}`
- Modify: `public/i18n/en.json`, `ar.json`
- Backend: add `pending-diff/` endpoint (repo `version_diff` already diffs vs predecessor; for a **draft** we diff draft vs head)

**Interfaces:**
- Consumes: Task 3 diff shape.
- Produces: `AssetContentService.pendingChanges(kind, slug, draftId)`, `commit(kind, slug, versionId, message)`.

- [ ] **Step 1: Backend pending-diff endpoint**

```python
# service
def get_pending_changes(self, slug, category, version_id, publisher_q=None) -> list[dict]:
    draft = self._get_editable_draft_or_400(self._get_asset_or_404(slug, category, publisher_q=publisher_q), version_id)
    language = draft.asset_language.language if draft.asset_language_id else draft.asset.language
    head = draft.asset.get_latest_version(language)
    return self.repo.diff_maps(self.repo.reconstruct_entries(head) if head else {}, self.repo._entries_map(draft))
```
Add `diff_maps(old_map, new_map) -> list[dict]` (extract the old/new comparison from `version_diff` into a shared helper both call). Endpoint: `GET .../versions/{version_id}/pending-diff/` (write perm), returns `list[ChangeOut]`.

- [ ] **Step 2: FE models + service**

```ts
// models
export interface ContentChange {
  ayah_id: number; sura: number; aya: number; surah_name: string;
  change_type: 'added' | 'modified' | 'removed'; old_text: string; new_text: string;
}
// service
pendingChanges(kind, slug, versionId): Observable<{ results: ContentChange[]; count: number }> {
  return this.http.get(`${this.versionBase(kind, slug, versionId)}pending-diff/`);
}
commit(kind, slug, versionId, message: string): Observable<ContentDraftVersion> {
  return this.http.post(`${this.versionBase(kind, slug, versionId)}publish/`, { message });
}
```

- [ ] **Step 3: Commit dialog in the grid**

Replace the current `publish()` with: flush pending → load `pendingChanges` → open an `nz-modal` with a **required** message textarea + a change summary (`+A ~M −R` and the changed-ayah refs). Confirm calls `commit(...)`; on success navigate back with a success toast; `commit_message_required`/`no_changes_to_publish` surfaced via the existing `showError` (friendly popups).

- [ ] **Step 4: i18n**

Add `ADMIN.CONTENT_EDITOR.COMMIT.{BUTTON, TITLE, MESSAGE_LABEL, MESSAGE_PLACEHOLDER, MESSAGE_REQUIRED, REVIEW, ADDED, MODIFIED, REMOVED, CONFIRM, CANCEL}` in en + ar; add `ERRORS.COMMIT_MESSAGE_REQUIRED`.

- [ ] **Step 5: Verify**

Run: `npx tsc --noEmit -p tsconfig.app.json`; `node -e "JSON.parse(require('fs').readFileSync('public/i18n/en.json'));JSON.parse(require('fs').readFileSync('public/i18n/ar.json'))"`; `npm run build`.

- [ ] **Step 6: Commit (staged for user)** — `feat(admin): commit dialog with required message and change review`.

---

## Task 6: Frontend — commit-log history with expandable diffs

**Files:**
- Modify: `src/app/features/admin/models/asset-versions.models.ts` (`created_by`, `change_counts`)
- Modify: `src/app/features/admin/services/asset-content.service.ts` (`versionDiff`)
- Modify: `src/app/features/admin/components/asset-versions-manager/*`
- Modify: `public/i18n/en.json`, `ar.json`

**Interfaces:**
- Consumes: Task 3 diff endpoint; list `created_by`/`change_counts`.

- [ ] **Step 1: Model + service**

```ts
// AssetVersion: add
created_by?: string | null;
change_counts?: { added: number; modified: number; removed: number } | null;
// service
versionDiff(kind, slug, versionId, page = 1, pageSize = 100): Observable<{ results: ContentChange[]; count: number }> {
  const params = new HttpParams().set('page', page).set('page_size', pageSize);
  return this.http.get(`${this.versionBase(kind, slug, versionId)}diff/`, { params });
}
```

- [ ] **Step 2: Commit-log rows**

In the versions manager, add to each row: the message (`summary`), author (`created_by`), and a compact change-count badge (`+1 ~3 −1`) when `change_counts` is present. Keep the `Active` badge, Download, Restore.

- [ ] **Step 3: Expandable diff panel**

Use `nz-table` expand (or a chevron toggle) per row; on first expand, call `versionDiff(...)` and render each change: `sura:aya`, a colored marker (added/modified/removed), and stacked old/new text. Paginate within the panel (page size 100) with a "load more" for large commits.

- [ ] **Step 4: i18n**

Add `…VERSIONS.{COMMIT_MESSAGE, AUTHOR, CHANGES, DIFF_ADDED, DIFF_MODIFIED, DIFF_REMOVED, DIFF_OLD, DIFF_NEW, DIFF_EMPTY, DIFF_LOAD_MORE}` in en + ar (both tafsir + translation blocks, as before).

- [ ] **Step 5: Verify**

Run: `npx tsc --noEmit -p tsconfig.app.json`; validate i18n JSON; `npm run build`; `npx eslint <changed files>`.

- [ ] **Step 6: Commit (staged for user)** — `feat(admin): commit-log history with expandable per-ayah diffs`.

---

## Final verification

- [ ] Backend: `.venv/bin/python -m pytest apps/content/ --create-db -q` all pass; `ruff check apps/content/` clean; `makemigrations --check` clean; `compilemessages --locale=ar` clean.
- [ ] Frontend: `tsc --noEmit` clean; `npm run build` clean; `eslint` clean; both i18n JSON valid.
- [ ] Manual smoke (run-app): edit a language → Commit with a message → appears in history with counts → expand shows the diff → download an old commit (reconstructed) → restore an old commit → it becomes active.
- [ ] Consumer download / samples still serve the head (unchanged).
- [ ] Hand to user for commits in each repo.
