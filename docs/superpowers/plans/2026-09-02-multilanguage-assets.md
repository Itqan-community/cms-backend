# Multi-language Text Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one text asset (translation/tafsir) hold a source language plus many translations, each with its own per-ayah content, version history, and draft; edited one language at a time; downloadable per language by consumers.

**Architecture:** Add an `AssetLanguage` registry row per supported language and tag each `AssetVersion` with its language (Approach B from the spec). `AssetVersion.asset` FK stays (low churn); a new `asset_language` FK adds language scoping. All existing per-ayah editing machinery (draft lifecycle, import/export, publish) now operates within a selected language. Consumers pick a language at download time; omitting it serves the source (backward compatible).

**Tech Stack:** Django + Django Ninja (backend, `itqan-cms-backend`); Angular 20 standalone + signals + ng-zorro + ag-grid (frontend, `cms-frontend`). Two separate repos in one workspace.

**Spec:** `docs/superpowers/specs/2026-09-02-multilanguage-assets-design.md`

## Global Constraints

- **Repo rule — the human commits.** Do NOT run `git commit`/`git push`. "Commit" steps are checkpoint markers; leave the changes staged/working and let the user commit. Never commit across both repos in one command (they are independent git repos).
- **Backend commands run from `itqan-cms-backend/`; frontend from `cms-frontend/`.** Never from the workspace root.
- **Python is `.venv/bin/python`** (no bare `python`). Tests: `.venv/bin/python -m pytest ...`. First run after a schema change needs `--create-db`; otherwise `--reuse-db` (default).
- **Backend test base class:** per-ayah/content tests use the project's `BaseTestCase` (raw `django.test.TestCase` kills the shared DB connection for the rest of the suite). Follow the existing `apps/content/tests/portal/test_asset_content.py` base class.
- **All user-facing `_()` strings** need `extendedmakemessages` + an Arabic `.po` entry; frontend user-facing text goes through ngx-translate in both `en.json` and `ar.json`.
- **`language` is a free-form code string** (`max_length=10`) everywhere — do not introduce a DB enum/table for it.
- **Service→Repository pattern for writes; direct-model reads for portal.** Errors via `ItqanError`/`NinjaErrorResponse`.
- **`AssetVersion.asset_id` must always equal `asset_language.asset_id`** — enforced in `save()`.

---

## File Structure

Backend (`itqan-cms-backend/`):
- `apps/content/models.py` — add `AssetLanguage`; add `AssetVersion.asset_language` + constraint + `save()` invariant; `Asset.get_latest_version(language=None)`.
- `apps/content/migrations/0053_*.py` — schema (AssetLanguage + nullable FK + draft constraint swap prep).
- `apps/content/migrations/0054_*.py` — data backfill.
- `apps/content/migrations/0055_*.py` — tighten (non-null FK, final draft constraint).
- `apps/content/repositories/asset_content.py` — language-aware draft/seed/create.
- `apps/content/services/asset_content.py` — language param through get-or-create/entries/publish; source-reference helper.
- `apps/content/services/asset_language.py` — **new**: add-language + list-languages service.
- `apps/content/api/portal/asset_content.py` — language on draft endpoint; source-reference in translation entries.
- `apps/content/api/portal/asset_languages.py` — **new**: list/add languages endpoints.
- `apps/content/api/internal/assets_download.py` — `?language`.
- `apps/content/api/internal/assets_detail.py` — `available_languages`.
- Tests under `apps/content/tests/`.

Frontend (`cms-frontend/`):
- `src/app/features/admin/models/asset-content.models.ts` — language models.
- `src/app/features/admin/services/asset-content.service.ts` — language-scoped calls.
- `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.*` — language switcher, source-reference column.
- gallery asset-detail component + download — language switcher.
- `public/i18n/en.json` + `ar.json`.

---

## Task 1: `AssetLanguage` model + `AssetVersion.asset_language` field (schema only)

**Files:**
- Modify: `apps/content/models.py` (add `AssetLanguage` after `Asset`; add field to `AssetVersion`)
- Create: `apps/content/migrations/0053_assetlanguage_and_asset_language_fk.py` (via makemigrations)
- Test: `apps/content/tests/models/test_asset_language.py`

**Interfaces:**
- Produces: `AssetLanguage(asset, language, is_source)` with `related_name="languages"`; `AssetVersion.asset_language` (FK, nullable at this task), `AssetVersion.asset_language_id`.

- [ ] **Step 1: Write the failing test**

```python
# apps/content/tests/models/test_asset_language.py
from django.db import IntegrityError
import pytest
from apps.content.tests.base import ContentModelTestBase  # match existing base used in content tests
from apps.content.models import Asset, AssetLanguage


class AssetLanguageModelTest(ContentModelTestBase):
    def test_unique_language_per_asset(self):
        asset = self.make_translation_asset(language="ar")
        AssetLanguage.objects.create(asset=asset, language="es")
        with pytest.raises(IntegrityError):
            AssetLanguage.objects.create(asset=asset, language="es")

    def test_only_one_source_per_asset(self):
        asset = self.make_translation_asset(language="ar")
        AssetLanguage.objects.create(asset=asset, language="ar", is_source=True)
        with pytest.raises(IntegrityError):
            AssetLanguage.objects.create(asset=asset, language="es", is_source=True)
```

> If there is no `ContentModelTestBase`/`make_translation_asset` helper, use `model_bakery.baker.make(Asset, category="translation", language="ar")` and the project `BaseTestCase`, mirroring `apps/content/tests/portal/test_asset_content.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_language.py --create-db -q`
Expected: FAIL (`AssetLanguage` does not exist / no such table).

- [ ] **Step 3: Add the model and field**

```python
# apps/content/models.py — add after the Asset class
class AssetLanguage(BaseModel):
    """One language an asset provides content in (source + translations)."""

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="languages")
    language = models.CharField(max_length=10, help_text="Language code, e.g. 'ar', 'es'")
    is_source = models.BooleanField(
        default=False,
        help_text="True for the asset's original/source language (at most one per asset).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["asset", "language"], name="unique_language_per_asset"),
            models.UniqueConstraint(
                fields=["asset"],
                condition=models.Q(is_source=True),
                name="unique_source_language_per_asset",
            ),
        ]

    def __str__(self):
        return f"AssetLanguage(asset_id={self.asset_id}, language={self.language}, source={self.is_source})"
```

```python
# apps/content/models.py — inside AssetVersion, after the `asset` FK
    asset_language = models.ForeignKey(
        "AssetLanguage",
        on_delete=models.PROTECT,
        related_name="versions",
        null=True,  # tightened to non-null in migration 0055 after backfill
        blank=True,
        help_text="Language rendition this version belongs to.",
    )
```

- [ ] **Step 4: Make the migration**

Run: `.venv/bin/python manage.py makemigrations content --name assetlanguage_and_asset_language_fk`
Expected: creates `0053_...` adding `AssetLanguage` + nullable `asset_language`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_language.py --create-db -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit (staged for user)**

```bash
git add apps/content/models.py apps/content/migrations/0053_*.py apps/content/tests/models/test_asset_language.py
# user commits: feat(content): add AssetLanguage registry and version language FK
```

---

## Task 2: Backfill data migration + tighten constraints

**Files:**
- Create: `apps/content/migrations/0054_backfill_asset_languages.py` (hand-written data migration)
- Create: `apps/content/migrations/0055_tighten_asset_language.py` (via makemigrations, then edit constraint)
- Modify: `apps/content/models.py` (`AssetVersion.asset_language` → non-null; swap draft constraint)
- Test: `apps/content/tests/migrations/test_backfill_asset_languages.py`

**Interfaces:**
- Consumes: `AssetLanguage`, `AssetVersion.asset_language` from Task 1.
- Produces: every existing `Asset` has one `is_source` `AssetLanguage` (language = `asset.language`); every `AssetVersion.asset_language` set; final constraint `unique_draft_version_per_asset_language`.

- [ ] **Step 1: Write the failing test (migration behavior via a post-migrate assertion)**

```python
# apps/content/tests/migrations/test_backfill_asset_languages.py
from apps.content.tests.base import ContentModelTestBase
from apps.content.models import Asset, AssetLanguage, AssetVersion
from model_bakery import baker


class BackfillAssetLanguagesTest(ContentModelTestBase):
    def test_every_asset_has_one_source_language_and_versions_linked(self):
        # Simulate the post-backfill invariant that the data migration guarantees.
        asset = baker.make(Asset, category="translation", language="ar")
        version = baker.make(AssetVersion, asset=asset)
        # After migrations run in the test DB, the backfill should have created
        # the source language and linked the version.
        source = AssetLanguage.objects.get(asset=asset, is_source=True)
        self.assertEqual("ar", source.language)
        version.refresh_from_db()
        self.assertEqual(source.id, version.asset_language_id)
```

> Note: because migrations run before objects created in the test exist, this test instead verifies the *forward function* directly. Refactor the backfill into a callable and test it explicitly (Step 3 shows the function; test it by creating asset+version with `asset_language=None`, calling the function, and asserting the links). Rewrite Step 1's body to call that function on rows you create with `asset_language=None`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest apps/content/tests/migrations/test_backfill_asset_languages.py --create-db -q`
Expected: FAIL.

- [ ] **Step 3: Write the data migration**

```python
# apps/content/migrations/0054_backfill_asset_languages.py
from django.db import migrations


def backfill(apps, schema_editor):
    Asset = apps.get_model("content", "Asset")
    AssetLanguage = apps.get_model("content", "AssetLanguage")
    AssetVersion = apps.get_model("content", "AssetVersion")

    for asset in Asset.objects.all().iterator():
        source, _ = AssetLanguage.objects.get_or_create(
            asset=asset, language=asset.language, defaults={"is_source": True}
        )
        if not source.is_source:
            source.is_source = True
            source.save(update_fields=["is_source"])
        AssetVersion.objects.filter(asset=asset, asset_language__isnull=True).update(asset_language=source)


def unbackfill(apps, schema_editor):
    AssetVersion = apps.get_model("content", "AssetVersion")
    AssetLanguage = apps.get_model("content", "AssetLanguage")
    AssetVersion.objects.update(asset_language=None)
    AssetLanguage.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0053_assetlanguage_and_asset_language_fk")]
    operations = [migrations.RunPython(backfill, unbackfill)]
```

- [ ] **Step 4: Tighten the model, then makemigrations for 0055**

```python
# apps/content/models.py — AssetVersion.asset_language: drop null/blank
    asset_language = models.ForeignKey(
        "AssetLanguage", on_delete=models.PROTECT, related_name="versions",
        help_text="Language rendition this version belongs to.",
    )
```

```python
# apps/content/models.py — AssetVersion.Meta.constraints: replace the draft constraint
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "asset_language"],
                condition=models.Q(state=VersionStateChoice.DRAFT),
                name="unique_draft_version_per_asset_language",
            ),
        ]
```

```python
# apps/content/models.py — AssetVersion.save(): enforce the invariant
    def save(self, *args, **kwargs):
        if self.asset_language_id and self.asset_id != self.asset_language.asset_id:
            self.asset_id = self.asset_language.asset_id
        super().save(*args, **kwargs)
```

Run: `.venv/bin/python manage.py makemigrations content --name tighten_asset_language`
Expected: `0055_...` alters `asset_language` to non-null and swaps the draft constraint. Verify it depends on `0054`.

- [ ] **Step 5: Apply and run**

Run:
```bash
.venv/bin/python manage.py migrate content
.venv/bin/python -m pytest apps/content/tests/migrations/test_backfill_asset_languages.py --create-db -q
```
Expected: migrations apply cleanly; PASS.

- [ ] **Step 6: Commit (staged for user)**

```bash
git add apps/content/models.py apps/content/migrations/0054_*.py apps/content/migrations/0055_*.py apps/content/tests/migrations/
# user commits: feat(content): backfill source AssetLanguage and enforce per-language drafts
```

---

## Task 3: `get_latest_version(language)` + language on repository draft creation

**Files:**
- Modify: `apps/content/models.py:261` (`Asset.get_latest_version`)
- Modify: `apps/content/repositories/asset_content.py` (`get_draft`, `create_draft_seeded_from`, `unique_version_name` scope)
- Test: `apps/content/tests/portal/test_asset_content.py` (extend) / `apps/content/tests/models/test_asset_language.py`

**Interfaces:**
- Consumes: `AssetLanguage`, `AssetVersion.asset_language` (Tasks 1–2).
- Produces:
  - `Asset.get_latest_version(language: str | None = None) -> AssetVersion | None`
  - `AssetContentRepository.get_draft(asset, asset_language) -> AssetVersion | None`
  - `AssetContentRepository.create_draft_seeded_from(asset, source_version, *, asset_language, name, summary, created_by_id) -> AssetVersion`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_latest_version_filters_by_language(self):
    asset = baker.make(Asset, category="translation", language="ar")
    ar = AssetLanguage.objects.create(asset=asset, language="ar", is_source=True)
    es = AssetLanguage.objects.create(asset=asset, language="es")
    v_ar = baker.make(AssetVersion, asset=asset, asset_language=ar, state=VersionStateChoice.PUBLISHED)
    v_es = baker.make(AssetVersion, asset=asset, asset_language=es, state=VersionStateChoice.PUBLISHED)
    self.assertEqual(v_es.id, asset.get_latest_version("es").id)
    self.assertEqual(v_ar.id, asset.get_latest_version("ar").id)
    self.assertEqual(v_ar.id, asset.get_latest_version().id)  # None -> source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_language.py -k get_latest_version --create-db -q`
Expected: FAIL (`get_latest_version()` takes no args).

- [ ] **Step 3: Implement**

```python
# apps/content/models.py
    def get_latest_version(self, language: str | None = None):
        qs = self.versions.filter(state=VersionStateChoice.PUBLISHED)
        lang = language or self.language
        qs = qs.filter(asset_language__language=lang)
        return qs.order_by("-created_at").first()
```

```python
# apps/content/repositories/asset_content.py — add asset_language scoping
    def get_draft(self, asset: Asset, asset_language: "AssetLanguage") -> AssetVersion | None:
        return self.asset_version_model.objects.filter(
            asset=asset, asset_language=asset_language, state=VersionStateChoice.DRAFT
        ).first()
```

```python
# create_draft_seeded_from: add asset_language kwarg, set it on create
    def create_draft_seeded_from(self, asset, source_version, *, asset_language, name, summary, created_by_id):
        draft = self.asset_version_model.objects.create(
            asset=asset, asset_language=asset_language, name=name, summary=summary,
            state=VersionStateChoice.DRAFT, created_by_id=created_by_id,
        )
        # ... existing entry-copy block unchanged ...
        return draft
```

> `unique_version_name` currently scopes name uniqueness to `asset`. Keep it asset-wide (version names remain distinct across the asset) — no change needed, but confirm the existing test still passes.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/models/test_asset_language.py apps/content/tests/portal/test_asset_content.py --create-db -q`
Expected: PASS (new + existing; fix any call sites of `get_draft`/`create_draft_seeded_from` surfaced by failures — they are updated in Task 4).

- [ ] **Step 5: Commit (staged for user)**

```bash
git add apps/content/models.py apps/content/repositories/asset_content.py apps/content/tests/
# user commits: feat(content): language-aware latest version and draft lookup
```

---

## Task 4: Language-scoped get-or-create draft (service) + add-language service

**Files:**
- Modify: `apps/content/services/asset_content.py` (`get_or_create_draft`, `_get_editable_draft_or_400`, `publish_draft` — thread `asset_language`)
- Create: `apps/content/services/asset_language.py` (list + add language)
- Test: `apps/content/tests/portal/test_asset_content.py`, `apps/content/tests/services/test_asset_language.py`

**Interfaces:**
- Consumes: Task 3 repo/model signatures.
- Produces:
  - `AssetContentService.get_or_create_draft(slug, category, *, language, created_by_id, publisher_q=None) -> AssetVersion` (language required; validated against `AssetLanguage`)
  - `AssetLanguageService.list_languages(slug, category, *, publisher_q=None) -> list[AssetLanguage]`
  - `AssetLanguageService.add_language(slug, category, *, language, publisher_q=None) -> AssetLanguage` (raises `ItqanError("language_exists", 400)`; never `is_source`)

- [ ] **Step 1: Write the failing tests**

```python
# apps/content/tests/services/test_asset_language.py
class AddLanguageServiceTest(AssetContentBaseTest):
    def test_add_language_creates_non_source_registry_row(self):
        lang = AssetLanguageService().add_language(
            self.translation.slug, CategoryChoice.TRANSLATION, language="es"
        )
        self.assertFalse(lang.is_source)
        self.assertEqual("es", lang.language)

    def test_add_duplicate_language_raises(self):
        AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")
        with self.assertRaises(ItqanError):
            AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")


# in test_asset_content.py
    def test_draft_is_per_language(self):
        # es draft and ar draft coexist; publishing es leaves ar draft intact
        svc = AssetContentService()
        AssetLanguageService().add_language(self.translation.slug, CategoryChoice.TRANSLATION, language="es")
        ar_draft = svc.get_or_create_draft(self.translation.slug, CategoryChoice.TRANSLATION, language="ar", created_by_id=self.user.id)
        es_draft = svc.get_or_create_draft(self.translation.slug, CategoryChoice.TRANSLATION, language="es", created_by_id=self.user.id)
        self.assertNotEqual(ar_draft.id, es_draft.id)
        self.assertEqual("ar", ar_draft.asset_language.language)
        self.assertEqual("es", es_draft.asset_language.language)
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/services/test_asset_language.py apps/content/tests/portal/test_asset_content.py -k "language" --create-db -q`
Expected: FAIL (`AssetLanguageService` missing; `get_or_create_draft` has no `language`).

- [ ] **Step 3: Implement the service changes**

```python
# apps/content/services/asset_language.py
from __future__ import annotations
from django.db.models import Q
from apps.content.models import AssetLanguage, CategoryChoice
from apps.content.services.asset_content import AssetContentService
from apps.core.ninja_utils.errors import ItqanError


class AssetLanguageService:
    def __init__(self) -> None:
        self._content = AssetContentService()

    def _asset(self, slug, category, publisher_q=None):
        return self._content._get_asset_or_404(slug, category, publisher_q=publisher_q)

    def list_languages(self, slug, category, *, publisher_q=None):
        asset = self._asset(slug, category, publisher_q)
        return list(asset.languages.order_by("-is_source", "language"))

    def add_language(self, slug, category, *, language, publisher_q=None):
        asset = self._asset(slug, category, publisher_q)
        if asset.languages.filter(language=language).exists():
            raise ItqanError(error_name="language_exists", message="Language already exists.", status_code=400)
        return AssetLanguage.objects.create(asset=asset, language=language, is_source=False)

    def get_asset_language_or_404(self, asset, language):
        obj = asset.languages.filter(language=language).first()
        if obj is None:
            raise ItqanError(error_name="language_not_available", message="Language not available.", status_code=404)
        return obj
```

```python
# apps/content/services/asset_content.py — get_or_create_draft gains `language`
    def get_or_create_draft(self, slug, category, *, language, created_by_id, publisher_q=None):
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        asset_language = AssetLanguageService().get_asset_language_or_404(asset, language)
        try:
            with transaction.atomic():
                locked_asset = Asset.objects.select_for_update().get(pk=asset.pk)
                source = locked_asset.get_latest_version(language)  # latest published of THIS language
                existing = self.repo.get_draft(locked_asset, asset_language)
                if existing is not None:
                    is_stale = source is not None and source.created_at > existing.created_at
                    if not is_stale:
                        return existing
                    self.repo.delete_version(existing)
                base_name = source.name if source else _("Draft")
                name = self.repo.unique_version_name(locked_asset, base_name)
                summary = source.summary if source else ""
                draft = self.repo.create_draft_seeded_from(
                    locked_asset, source, asset_language=asset_language, name=name, summary=summary, created_by_id=created_by_id,
                )
        except IntegrityError:
            existing = self.repo.get_draft(asset, asset_language)
            if existing is not None:
                return existing
            raise
        return draft
```

> To avoid a circular import (`asset_language.py` imports `AssetContentService` which now references `AssetLanguageService`), import `AssetLanguageService` lazily inside `get_or_create_draft`, or move `get_asset_language_or_404` to a small shared helper. Prefer the lazy import.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/services/test_asset_language.py apps/content/tests/portal/test_asset_content.py --create-db -q`
Expected: PASS.

- [ ] **Step 5: Commit (staged for user)**

```bash
git add apps/content/services/ apps/content/tests/
# user commits: feat(content): per-language get-or-create draft and add-language service
```

---

## Task 5: Portal API — language endpoints + language on draft + source reference

**Files:**
- Create: `apps/content/api/portal/asset_languages.py` (GET list, POST add)
- Modify: `apps/content/api/portal/asset_content.py` (`get_or_create_draft` accepts `language`; translation entries include source reference)
- Modify: wherever the portal router registers sub-routers (register `asset_languages` router)
- Test: `apps/content/tests/portal/test_asset_languages.py`, extend `test_asset_content.py`

**Interfaces:**
- Consumes: Task 4 services.
- Produces:
  - `GET content/{category}/{slug}/languages/` → `list[LanguageOut]` (`{language, is_source}`)
  - `POST content/{category}/{slug}/languages/` body `{language}` → `LanguageOut`
  - `POST content/{category}/{slug}/draft/` body `{language}` → `DraftVersionOut`
  - `EntryOut` gains optional `source_text: str | None` (populated only when editing a non-source language)

- [ ] **Step 1: Write the failing tests**

```python
# apps/content/tests/portal/test_asset_languages.py
def test_list_languages_returns_source_first(self):
    self.authenticate_user(self.user); self.give_permission(self.user, PermissionChoice.PORTAL_READ_TRANSLATION)
    r = self.client.get(f"/portal/content/translations/{self.translation.slug}/languages/")
    self.assertEqual(200, r.status_code, r.content)
    body = r.json()
    self.assertTrue(body[0]["is_source"])

def test_add_language(self):
    self.authenticate_user(self.user); self.give_permission(self.user, PermissionChoice.PORTAL_UPDATE_TRANSLATION)
    r = self.client.post(f"/portal/content/translations/{self.translation.slug}/languages/",
                         data={"language": "es"}, content_type="application/json")
    self.assertEqual(200, r.status_code, r.content)
    self.assertFalse(r.json()["is_source"])
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/test_asset_languages.py --create-db -q`
Expected: FAIL (404 route not found).

- [ ] **Step 3: Implement endpoints**

```python
# apps/content/api/portal/asset_languages.py
from typing import Literal
from ninja import Schema
from apps.content.services.asset_language import AssetLanguageService
from apps.content.api.portal.asset_content import _resolve  # reuse category+permission resolver
from apps.core.ninja_utils.errors import NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.TRANSLATIONS])


class LanguageOut(Schema):
    language: str
    is_source: bool


class AddLanguageIn(Schema):
    language: str


@router.get("content/{category}/{slug}/languages/", response={200: list[LanguageOut], 404: NinjaErrorResponse[Literal["unsupported_content_category"]]})
def list_languages(request: Request, category: str, slug: str):
    resolved = _resolve(category, request, write=False)
    return AssetLanguageService().list_languages(slug, resolved, publisher_q=request.publisher_q())


@router.post("content/{category}/{slug}/languages/", response={200: LanguageOut, 400: NinjaErrorResponse[Literal["language_exists"]], 404: NinjaErrorResponse[Literal["unsupported_content_category"]]})
def add_language(request: Request, category: str, slug: str, data: AddLanguageIn):
    resolved = _resolve(category, request, write=True)
    return AssetLanguageService().add_language(slug, resolved, language=data.language, publisher_q=request.publisher_q())
```

```python
# apps/content/api/portal/asset_content.py — draft endpoint accepts language
class DraftIn(Schema):
    language: str

@router.post("content/{category}/{slug}/draft/", response={...})  # keep existing response map
def get_or_create_draft(request: Request, category: str, slug: str, data: DraftIn) -> AssetVersion:
    resolved = _resolve(category, request, write=True)
    return AssetContentService().get_or_create_draft(
        slug, resolved, language=data.language,
        created_by_id=getattr(request.user, "id", None), publisher_q=request.publisher_q(),
    )
```

Register the new router where portal routers are wired (search for where `asset_content.router` is added, add `asset_languages.router` beside it).

- [ ] **Step 4: Source reference on translation entries**

Add `source_text: str | None = None` to `EntryOut`. In the service `get_entries`, when the version's `asset_language` is not the source, build a `{ayah_id: source_text}` map from `asset.get_latest_version(source_language).entries` and attach it to each returned entry (as an attribute the schema resolver reads). Test:

```python
def test_entries_include_source_text_for_translation(self):
    # seed ar published entry text; create es draft; GET entries returns source_text from ar
    ...
    self.assertEqual("<ar text>", body[0]["source_text"])

def test_entries_source_text_null_when_editing_source(self):
    # editing ar (source) -> source_text is None
    ...
    self.assertIsNone(body[0]["source_text"])
```

Implement by resolving the source map in the service and setting `entry.source_text` on each ORM object before return (Ninja resolves attributes), or add a `resolve_source_text` staticmethod on `EntryOut` backed by a per-request cache.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/portal/ --create-db -q`
Expected: PASS (update the existing `get_or_create_draft` tests to send `{"language": "ar"}`).

- [ ] **Step 6: Commit (staged for user)**

```bash
git add apps/content/api/portal/ apps/content/services/ apps/content/tests/portal/
# user commits: feat(portal): language endpoints and source-reference entries
```

---

## Task 6: Consumer delivery — `?language` download + `available_languages`

**Files:**
- Modify: `apps/content/api/internal/assets_download.py` (accept `language`)
- Modify: `apps/content/api/internal/assets_detail.py` (add `available_languages`)
- Test: `apps/content/tests/internal/test_assets_download.py`, `.../test_assets_detail.py`

**Interfaces:**
- Consumes: `Asset.get_latest_version(language)`, `AssetLanguage`.
- Produces: `download?language=xx` (404 `language_not_available` for unknown); `available_languages: list[str]` on asset detail (only languages with ≥1 published version).

- [ ] **Step 1: Write the failing tests**

```python
def test_download_language_serves_that_language_file(self):
    # asset with ar+es published versions each with a file_url
    r = self.client.get(f"/internal/assets/{asset.id}/download/?language=es")
    self.assertEqual(200, r.status_code, r.content)
    self.assertIn("<es file marker>", r.json()["download_url"])

def test_download_unknown_language_404(self):
    r = self.client.get(f"/internal/assets/{asset.id}/download/?language=zz")
    self.assertEqual(404, r.status_code)

def test_available_languages_excludes_draft_only(self):
    # ar published, es draft-only -> available == ["ar"]
    r = self.client.get(f"/internal/assets/{asset.id}/")
    self.assertEqual(["ar"], r.json()["available_languages"])
```

- [ ] **Step 2: Run to verify fail**

Run: `.venv/bin/python -m pytest apps/content/tests/internal/ --create-db -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# assets_download.py — signature and resolution
def download_asset(request: Request, id: int, language: str | None = None):
    asset = get_object_or_404(Asset, request.publisher_q("publisher"), restricted_for_tenant=False, id=id)
    if not user_has_access(request.user, asset):
        raise PermissionDenied(_("You do not have access to this asset"))
    if language is not None and not asset.languages.filter(language=language).exists():
        raise Http404(str(_("Language not available for this asset")))
    asset_latest_version = asset.get_latest_version(language)  # None -> source
    # ... rest unchanged (file_url checks, presign/local, usage event) ...
```

Add `"language": language` into the `UsageEvent` metadata dict.

```python
# assets_detail.py — add to the out schema + resolver
    available_languages: list[str]

    @staticmethod
    def resolve_available_languages(obj: Asset) -> list[str]:
        published = (obj.versions.filter(state=VersionStateChoice.PUBLISHED)
                     .values_list("asset_language__language", flat=True).distinct())
        return sorted(set(published))
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest apps/content/tests/internal/ --create-db -q`
Expected: PASS.

- [ ] **Step 5: Full backend suite + lint**

Run:
```bash
.venv/bin/python -m pytest apps/content/ --create-db -q
.venv/bin/ruff check apps/content/
.venv/bin/python manage.py makemigrations --check --dry-run
```
Expected: all pass; no pending migrations.

- [ ] **Step 6: Commit (staged for user)**

```bash
git add apps/content/api/internal/ apps/content/tests/internal/
# user commits: feat(internal): per-language download and available_languages
```

---

## Task 7: Frontend — models + service (language-scoped)

**Files (all in `cms-frontend/`):**
- Modify: `src/app/features/admin/models/asset-content.models.ts`
- Modify: `src/app/features/admin/services/asset-content.service.ts`
- Test: `src/app/features/admin/services/asset-content.service.spec.ts` (if present) or add one

**Interfaces:**
- Produces: `AssetLanguage {language: string; is_source: boolean}`; `ContentEntry.source_text?: string | null`; service methods `listLanguages(kind, slug)`, `addLanguage(kind, slug, language)`, `createDraft(kind, slug, language)`.

- [ ] **Step 1: Add model types**

```ts
// asset-content.models.ts
export interface AssetLanguage { language: string; is_source: boolean; }
// ContentEntry: add
  source_text?: string | null;
```

- [ ] **Step 2: Add service methods**

```ts
// asset-content.service.ts
listLanguages(kind: AssetVersionParentKind, slug: string) {
  return this.http.get<AssetLanguage[]>(`${this.base(kind, slug)}/languages/`);
}
addLanguage(kind: AssetVersionParentKind, slug: string, language: string) {
  return this.http.post<AssetLanguage>(`${this.base(kind, slug)}/languages/`, { language });
}
// createDraft now sends language
createDraft(kind: AssetVersionParentKind, slug: string, language: string) {
  return this.http.post<ContentDraftVersion>(`${this.base(kind, slug)}/draft/`, { language });
}
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit -p tsconfig.app.json`
Expected: no errors (update existing `createDraft` callers to pass a language — done in Task 8).

- [ ] **Step 4: Commit (staged for user)**

```bash
git add src/app/features/admin/models/ src/app/features/admin/services/
# user commits: feat(admin): language-scoped content service
```

---

## Task 8: Frontend — language switcher + add-language in the editor

**Files:**
- Modify: `asset-content-grid.component.ts` / `.html`
- Modify: `public/i18n/en.json`, `public/i18n/ar.json`
- Create: a small ISO-639 list constant `src/app/features/admin/utils/iso-639.util.ts`

**Interfaces:**
- Consumes: Task 7 service.
- Produces: `selectedLanguage` signal drives which language's draft/entries load; `languages` signal from `listLanguages`.

- [ ] **Step 1: Add signals + load languages on init**

```ts
readonly languages = signal<AssetLanguage[]>([]);
readonly selectedLanguage = signal<string | null>(null);
// ngOnInit: listLanguages(...).subscribe(ls => { this.languages.set(ls);
//   this.selectedLanguage.set(ls.find(l => l.is_source)?.language ?? ls[0]?.language ?? null);
//   this.loadForLanguage(); });
```

- [ ] **Step 2: Reload draft+entries when language changes**

`loadForLanguage()` calls `createDraft(kind, slug, this.selectedLanguage()!)` then loads entries for that draft. Switching language flushes pending edits of the current language first (reuse `flushPending`).

- [ ] **Step 3: Toolbar UI**

Add an `nz-select` bound to `selectedLanguage` (options from `languages()`, source labeled e.g. "Arabic (source)") and an "Add language" button opening an `nz-modal` with an `nz-select` of ISO-639 options; on OK call `addLanguage(...)`, append to `languages()`, switch to it.

- [ ] **Step 4: i18n**

Add `ADMIN.CONTENT_EDITOR.LANGUAGE.{LABEL, ADD, ADD_TITLE, SOURCE_SUFFIX, PICK}` to `en.json` and `ar.json`.

- [ ] **Step 5: Typecheck + JSON validate**

Run: `npx tsc --noEmit -p tsconfig.app.json && node -e "JSON.parse(require('fs').readFileSync('public/i18n/en.json'));JSON.parse(require('fs').readFileSync('public/i18n/ar.json'));console.log('ok')"`
Expected: clean.

- [ ] **Step 6: Commit (staged for user)**

```bash
git add src/app/features/admin/ public/i18n/
# user commits: feat(admin): language switcher and add-language in content editor
```

---

## Task 9: Frontend — source-reference column when editing a translation

**Files:**
- Modify: `asset-content-grid.component.ts` (`buildColumnDefs`)

**Interfaces:**
- Consumes: `ContentEntry.source_text`, `selectedLanguage`, `languages`.

- [ ] **Step 1: Compute `isEditingSource`**

```ts
readonly isEditingSource = computed(() =>
  this.languages().find(l => l.language === this.selectedLanguage())?.is_source ?? true);
```

- [ ] **Step 2: Conditionally insert the source column**

In `buildColumnDefs()`, when `!isEditingSource()`, insert a read-only column before `text`:

```ts
{ field: 'source_text', headerName: this.sourceHeader(), editable: false,
  flex: 2, wrapText: true, autoHeight: true, cellStyle: { direction: 'rtl' } }
```

Rebuild column defs whenever `selectedLanguage` changes (effect calling `gridApi.setGridOption('columnDefs', ...)`).

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit -p tsconfig.app.json`
Expected: clean.

- [ ] **Step 4: Manual check via run-app skill (optional)**

Open a translation asset, add "es", confirm the Arabic source shows read-only left of the editable Spanish column; switch to Arabic → source column disappears.

- [ ] **Step 5: Commit (staged for user)**

```bash
git add src/app/features/admin/
# user commits: feat(admin): source reference column for translation editing
```

---

## Task 10: Frontend — gallery language switcher + per-language download

**Files:**
- Modify: gallery asset-detail component (`src/app/features/gallery/pages/asset-details/asset-details.page.*`)
- Modify: the download call to pass `?language`
- Modify: `public/i18n/en.json`, `ar.json`

**Interfaces:**
- Consumes: `available_languages` on the asset detail response; download endpoint `?language`.

- [ ] **Step 1: Read `available_languages` into a signal; default to first**

- [ ] **Step 2: Render an `nz-select` when `available_languages.length > 1`**

- [ ] **Step 3: Pass the selected language to the download request** (`?language=<sel>`).

- [ ] **Step 4: i18n** — `GALLERY.LANGUAGE.LABEL` in both files.

- [ ] **Step 5: Typecheck + build**

Run: `npx tsc --noEmit -p tsconfig.app.json` then `npm run build`
Expected: clean.

- [ ] **Step 6: Commit (staged for user)**

```bash
git add src/app/features/gallery/ public/i18n/
# user commits: feat(gallery): per-language download switcher
```

---

## Final verification

- [ ] Backend: `.venv/bin/python -m pytest apps/content/ --create-db -q` (all pass), `.venv/bin/ruff check apps/content/` clean, `makemigrations --check` clean.
- [ ] Frontend: `npx tsc --noEmit -p tsconfig.app.json` clean, `npm run build` clean, both i18n JSON valid.
- [ ] Manual smoke (run-app skill): add a language, edit it with source reference visible, publish it, confirm the source language draft is untouched, and download the new language from the gallery.
- [ ] Hand to user for commits in each repo.
