# Asset Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give text assets (translations, tafsirs) a surah / ayah / word / page template that is chosen at creation, immutable afterwards, drives the storage granularity of their content rows, and is shown as a badge in the UI.

**Architecture:** `AssetVersionEntry` and `AssetVersionChange` gain three nullable sibling unit columns beside the existing `ayah` FK (`sura`, `word`, `page_no`), with a check constraint that exactly one is set — an additive migration that never rewrites an existing row. A single `UnitSpec` descriptor module holds the four-way branch; the entries endpoint enumerates the template's canonical unit set virtually and left-joins stored text, so a new surah asset shows 114 empty rows having written zero rows. Page templates reference a reusable `MushafLayout` (name + page count).

**Tech Stack:** Python 3.13, Django 5.2, django-ninja, django-modeltranslation, PostgreSQL, uv, pytest — backend. Angular (standalone components, signals), AG Grid Community, ng-zorro-antd, ngx-translate — frontend.

**Spec:** `docs/superpowers/specs/2026-09-17-asset-templates-design.md` (in `itqan-cms-backend`). Read it before starting; this plan argues from it.

## Global Constraints

- **Repos are separate.** Backend: `itqan-cms-backend`. Frontend: `cms-frontend`. Never run a command for one from the other's directory.
- **Branch:** `feat/asset-templates`, cut from `staging`, in each repo. PRs target `staging`. Never commit directly to `staging` or `main`.
- **Commit convention:** Conventional Commits, enforced by a `commit-msg` pre-commit hook. `feat:` bumps MINOR, `fix:`/`perf:` bump PATCH.
- **Tests:** `pytest`, never `python manage.py test`. Use the `.venv` virtualenv first. Every test class extends `apps.core.tests.base.BaseTestCase` — a raw `django.test.TestCase` kills the DB connection for the rest of the suite.
- **Test naming:** `test_<function_name>_where<criteria>_should<expected_results>`.
- **Test structure:** explicit `# Arrange`, `# Act`, `# Assert` comments in every test.
- **Auth in tests:** call `self.authenticate_user(...)` inside the test body, never in `setUp`/`setUpClass`.
- **4xx assertions:** assert the `error_name` in the response body, never just the status code.
- **Patching:** import the real symbol and use `patch.object(module, symbol.__name__)` at the call site. No hardcoded dotted-path strings.
- **Type hints:** every function is type hinted except `@router.`-decorated endpoint views.
- **Schemas:** use `AwareDatetime` (pydantic), never bare `datetime`, in any Ninja `Schema`.
- **Errors:** `apps.core.ninja_utils.errors.ItqanError` for 4xx. Its `message` is **always** wrapped in `gettext_lazy as _`. Document every error in the endpoint's `response={}` with `NinjaErrorResponse[Literal["..."]]`.
- **Architecture:** WRITE operations go Service → Repository → ORM. Portal READ operations (GET list/retrieve in `apps/*/api/portal/`) query the Model directly in the view — no Service, no Repository.
- **Localization gate (hard):** after adding any `_(...)` string, run `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header`, fill every new `msgstr` in `locale/ar/LC_MESSAGES/django.po`, and verify `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null` reports **0 untranslated**. Then `compilemessages`.
- **The test database ships with NO Quran data** (`Sura`, `Ayah`, `Word` are all empty; `--reuse-db` is on). The codebase's established pattern is that each test bakes the rows it needs — see `apps/content/tests/portal/test_asset_content.py:43` and `apps/content/tests/models/test_asset_version_change.py:14`. **Never assert against the canonical counts 114 / 6236 / 77431, and never call `Sura.objects.first()` expecting a row.** Bake explicitly and assert relative to what you baked. **Task 3 creates `apps/content/tests/quran_data.py`**; every later task that needs Quran rows imports `QuranDataMixin` from it and mixes it into the test class (`class Foo(QuranDataMixin, BaseTestCase)`), then calls `self.bake_quran()` in `setUp`:

```python
"""Minimal Quran rows for tests. The test DB ships empty and there is no
global fixture, so each test class bakes exactly what it asserts against."""

from model_bakery import baker

from apps.quran.models import Ayah, Sura, Word


class QuranDataMixin:
    def bake_quran(self):
        """Minimal Quran rows: 2 suras, 3 ayahs, 2 words. Ids are explicit so
        entries and assertions can reference them directly."""
        self.sura1 = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=2)
        self.sura2 = baker.make(Sura, id=2, name="البقرة", transliterated_name="Al-Baqara", ayas_count=1)
        self.ayah1 = baker.make(Ayah, id=1, sura=self.sura1, number_in_sura=1, text="ayah 1")
        self.ayah2 = baker.make(Ayah, id=2, sura=self.sura1, number_in_sura=2, text="ayah 2")
        self.ayah3 = baker.make(Ayah, id=3, sura=self.sura2, number_in_sura=1, text="ayah 3")
        self.word1 = baker.make(Word, id=1, sura=self.sura1, ayah=self.ayah1, position_in_ayah=1, text="w1")
        self.word2 = baker.make(Word, id=2, sura=self.sura1, ayah=self.ayah1, position_in_ayah=2, text="w2")
```

  With those rows: `Sura.objects.count() == 2`, `Ayah.objects.count() == 3`, `Word.objects.count() == 2`. Assert those numbers, not the canonical ones. Page-template assertions are exempt — they derive from `layout.page_count`, not Quran data.
- **Do not rename a pushed frontend branch** — it has previously closed an open PR rather than retargeting it.
- **`sentry-sdk` is a prod-only extra.** It is absent in CI and dev, so never import it in test code; stub the binding instead.

### Vocabulary locked by the spec

| Term | Exact value |
| --- | --- |
| Template values | `"surah"`, `"ayah"`, `"word"`, `"page"` |
| Template labels | "Surah based", "Ayah based", "Word based", "Page based" |
| Layout model | `MushafLayout` (fields: `name`, `page_count`) |
| Unit columns | `sura`, `ayah`, `word`, `page_no` |
| New errors | `asset_template_immutable`, `mushaf_layout_required`, `mushaf_layout_not_allowed`, `mushaf_layout_not_found` |

---

## File Structure

### Backend — `itqan-cms-backend`

| File | Responsibility |
| --- | --- |
| `apps/content/models.py` (modify) | `AssetTemplateChoice`, `MushafLayout`, `Asset.template`/`mushaf_layout`, unit columns + constraints on `AssetVersionEntry`/`AssetVersionChange`, `Asset.save()` immutability guard |
| `apps/content/translation.py` (modify) | Register `MushafLayout` for `name_ar`/`name_en` |
| `apps/content/services/asset_templates.py` (**create**) | `UnitSpec` — the only place the four-way branch lives |
| `apps/content/repositories/mushaf_layout.py` (**create**) | ORM access for `MushafLayout` writes |
| `apps/content/services/mushaf_layout.py` (**create**) | `MushafLayout` business rules |
| `apps/content/api/portal/mushaf_layouts.py` (**create**) | Portal CRUD (auto-discovered router) |
| `apps/content/repositories/asset_content.py` (modify) | Unit-aware entry read/write, virtual enumeration, CSV export |
| `apps/content/services/asset_content.py` (modify) | Unit-aware service paths, template/unit invariant |
| `apps/content/services/asset_content_import.py` (modify) | Template-aware CSV parsing |
| `apps/content/api/portal/asset_content.py` (modify) | `EntryOut`/`ChangeOut`/`EntryPatchRow` reshape, `sura` filter param |
| `apps/content/api/portal/translations.py`, `tafsirs.py` (modify) | `template`/`mushaf_layout_id` on create; template on list/detail/filters |
| `apps/content/services/translation.py`, `tafsir.py` (modify) | Template validation on create, immutability guard on update |
| `apps/content/api/portal/asset_review.py` (modify) | Template-aware `ReviewChangeOut` |
| `apps/content/repositories/asset_review.py` (modify) | Widen `select_related` to all four units |
| `apps/content/services/asset_verse_text.py` (modify) | Restrict verse sampling to ayah-template assets |
| `apps/core/permissions.py` (modify) | Four `PORTAL_*_MUSHAF_LAYOUT` permissions + implications |
| `apps/core/ninja_utils/tags.py` (modify) | `MUSHAF_LAYOUTS` tag |
| `apps/content/admin.py` (modify) | Readonly template fields after creation; `MushafLayout` admin |
| `apps/content/migrations/0062`–`0066` (**create**) | Schema, backfill, constraints |

### Frontend — `cms-frontend`

| File | Responsibility |
| --- | --- |
| `src/app/shared/components/asset-template-badge/` (**create**) | The "Ayah based" indicator, used in three places |
| `src/app/features/admin/services/mushaf-layouts.service.ts` (**create**) | Layout list for the selector |
| `src/app/features/admin/services/asset-content.service.ts` (modify) | Unit-shaped entry types, `sura` filter param |
| `src/app/features/admin/translations/components/translation-form/` (modify) | Template + layout selectors |
| `src/app/features/admin/tafsirs/components/tafsir-form/` (modify) | Template + layout selectors |
| `src/app/features/admin/components/asset-content-grid/` (modify) | Template-driven columns; row model per template |
| `src/app/features/admin/models/asset-review.models.ts` (modify) | `ReviewChange` keyed by unit |
| `src/app/features/admin/components/asset-review-grid/` (modify) | Render the unit label |
| `src/app/features/gallery/components/asset-card/` (modify) | Badge |
| `public/i18n/ar.json`, `public/i18n/en.json` (modify) | Badge, selector, tooltip strings |

---
## Phase 1 — Schema, backfill, immutability (backend)

Nothing in this phase is user-visible. It lands independently.

### Task 1: `MushafLayout` model and `AssetTemplateChoice`

**Files:**
- Modify: `apps/content/models.py`
- Modify: `apps/content/translation.py`
- Create: `apps/content/migrations/0062_mushaf_layout.py` (generated)
- Test: `apps/content/tests/models/test_mushaf_layout.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `AssetTemplateChoice` (TextChoices with members `SURAH`, `AYAH`, `WORD`, `PAGE` whose values are `"surah"`, `"ayah"`, `"word"`, `"page"`); `MushafLayout` model with fields `name: str`, `page_count: int`, plus modeltranslation's `name_ar` / `name_en`.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/models/test_mushaf_layout.py`:

```python
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from apps.content.models import AssetTemplateChoice, MushafLayout
from apps.core.tests.base import BaseTestCase


class MushafLayoutModelTests(BaseTestCase):
    def test_mushaf_layout_where_name_duplicated_should_raise_integrity_error(self):
        # Arrange
        MushafLayout.objects.create(name="Madani 604", page_count=604)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            MushafLayout.objects.create(name="Madani 604", page_count=500)

    def test_mushaf_layout_where_page_count_is_zero_should_fail_validation(self):
        # Arrange
        layout = MushafLayout(name="Broken", page_count=0)

        # Act / Assert
        with self.assertRaises(ValidationError):
            layout.full_clean()

    def test_asset_template_choice_where_listed_should_expose_four_values(self):
        # Arrange / Act
        values = set(AssetTemplateChoice.values)

        # Assert
        self.assertEqual(values, {"surah", "ayah", "word", "page"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/models/test_mushaf_layout.py -v`
Expected: FAIL — `ImportError: cannot import name 'AssetTemplateChoice'`.

- [ ] **Step 3: Add the choice set and the model**

In `apps/content/models.py`, beside the other `TextChoices` near the top (after `StatusChoice`):

```python
class AssetTemplateChoice(models.TextChoices):
    """Granularity of a text asset's content rows.

    Chosen when the asset is created and immutable afterwards: it determines
    which unit column every ``AssetVersionEntry`` for the asset is keyed to.
    """

    SURAH = "surah", _("Surah based")
    AYAH = "ayah", _("Ayah based")
    WORD = "word", _("Word based")
    PAGE = "page", _("Page based")
```

Add `MushafLayout` beside `Reciter` / `Riwayah` / `Qiraah`:

```python
class MushafLayout(BaseModel):
    """A printed mushaf's pagination, referenced by page-based text assets.

    Pages are opaque numbered slots (1..``page_count``). There is deliberately
    no page-to-ayah mapping: an ayah can straddle a page boundary, so a
    page-to-ayah-range map would be lossy.
    """

    name = models.CharField(max_length=128, unique=True, help_text="Layout name, e.g. 'Madani 604'")
    page_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of pages in this mushaf printing",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"MushafLayout(name={self.name}, pages={self.page_count})"
```

`MinValueValidator` is already imported at the top of the file.

In `apps/content/translation.py`, add `MushafLayout` to the import from `.models` and register it:

```python
@register(MushafLayout)
class MushafLayoutTranslationOptions(TranslationOptions):
    fields = ("name",)
```

- [ ] **Step 4: Generate and inspect the migration**

Run: `.venv/bin/python manage.py makemigrations content --name mushaf_layout`
Expected: creates `0062_mushaf_layout.py` with `CreateModel` for `MushafLayout` including `name`, `name_ar`, `name_en`, `page_count`.

Open the file and confirm the three `name*` columns are present. If `name_ar`/`name_en` are missing, `translation.py` was not updated — fix it and regenerate.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/pytest apps/content/tests/models/test_mushaf_layout.py -v`
Expected: 3 passed.

- [ ] **Step 6: Localization**

Four new `_()` strings were added (the template labels). Run:

```bash
.venv/bin/python manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header
```

Add the Arabic translations in `locale/ar/LC_MESSAGES/django.po`:

| msgid | msgstr |
| --- | --- |
| `Surah based` | `حسب السورة` |
| `Ayah based` | `حسب الآية` |
| `Word based` | `حسب الكلمة` |
| `Page based` | `حسب الصفحة` |

Verify: `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null`
Expected: 0 untranslated messages, no errors.

- [ ] **Step 7: Commit**

```bash
git add apps/content/models.py apps/content/translation.py \
        apps/content/migrations/0062_mushaf_layout.py \
        apps/content/tests/models/test_mushaf_layout.py \
        locale/ar/LC_MESSAGES/django.po
git commit -m "feat: add MushafLayout model and AssetTemplateChoice"
```

---

### Task 2: `Asset.template` and `Asset.mushaf_layout` with backfill

**Files:**
- Modify: `apps/content/models.py`
- Create: `apps/content/migrations/0063_asset_template_fields.py` (generated)
- Create: `apps/content/migrations/0064_backfill_asset_template.py` (hand-written)
- Create: `apps/content/migrations/0065_asset_template_constraints.py` (generated)
- Test: `apps/content/tests/models/test_asset_template.py`
- Test: `apps/content/tests/migrations/test_backfill_asset_template.py`

**Interfaces:**
- Consumes: `AssetTemplateChoice`, `MushafLayout` (Task 1).
- Produces: `Asset.template: str | None`, `Asset.mushaf_layout: MushafLayout | None`, and the constraints `asset_template_required_for_text` and `asset_mushaf_layout_consistency`.

The migration order is load-bearing: **0064 must run before 0065**, or the constraint fails against pre-existing rows.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/models/test_asset_template.py`:

```python
from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.tests.base import BaseTestCase


class AssetTemplateConstraintTests(BaseTestCase):
    def test_asset_where_translation_has_no_template_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(Asset, category=CategoryChoice.TRANSLATION, template=None)

    def test_asset_where_font_has_a_template_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(Asset, category=CategoryChoice.FONT, template=AssetTemplateChoice.AYAH)

    def test_asset_where_page_template_has_no_layout_should_raise_integrity_error(self):
        # Arrange / Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(
                Asset,
                category=CategoryChoice.TRANSLATION,
                template=AssetTemplateChoice.PAGE,
                mushaf_layout=None,
            )

    def test_asset_where_ayah_template_has_a_layout_should_raise_integrity_error(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            baker.make(
                Asset,
                category=CategoryChoice.TRANSLATION,
                template=AssetTemplateChoice.AYAH,
                mushaf_layout=layout,
            )

    def test_asset_where_page_template_has_a_layout_should_save(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Assert
        self.assertEqual(asset.mushaf_layout_id, layout.id)
        self.assertEqual(asset.template, AssetTemplateChoice.PAGE)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/models/test_asset_template.py -v`
Expected: FAIL — `TypeError`/`FieldError` on the unknown `template` keyword.

- [ ] **Step 3: Add the fields**

In `apps/content/models.py`, inside `Asset`, after the `category` field:

```python
    template = models.CharField(
        max_length=10,
        choices=AssetTemplateChoice,
        null=True,
        blank=True,
        help_text=(
            "Content granularity for text assets (translation / tafsir). "
            "Chosen at creation and immutable afterwards. NULL for every other category."
        ),
    )

    mushaf_layout = models.ForeignKey(
        "MushafLayout",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="Pagination this asset follows. Required when template is 'page', forbidden otherwise.",
    )
```

- [ ] **Step 4: Add the constraints**

Append to the existing `Asset.Meta.constraints` list (which already holds `asset_recitation_fields_consistency` and `asset_external_url_consistency`):

```python
            models.CheckConstraint(
                condition=models.Q(
                    category__in=[CategoryChoice.TRANSLATION, CategoryChoice.TAFSIR],
                    template__isnull=False,
                )
                | models.Q(
                    ~models.Q(category__in=[CategoryChoice.TRANSLATION, CategoryChoice.TAFSIR]),
                    template__isnull=True,
                ),
                name="asset_template_required_for_text",
            ),
            models.CheckConstraint(
                # Three branches, AND an explicit template__isnull=False on the
                # first. Every branch must be NULL-free: `template = 'page'` is
                # SQL NULL when template IS NULL, so without the guard branch A
                # yields NULL for a (template NULL, layout SET) row, and
                # NULL OR FALSE OR FALSE = NULL, which Postgres accepts as
                # satisfied — letting a font asset carry a mushaf layout.
                condition=models.Q(
                    template=AssetTemplateChoice.PAGE,
                    template__isnull=False,
                    mushaf_layout__isnull=False,
                )
                | models.Q(
                    ~models.Q(template=AssetTemplateChoice.PAGE),
                    template__isnull=False,
                    mushaf_layout__isnull=True,
                )
                | models.Q(template__isnull=True, mushaf_layout__isnull=True),
                name="asset_mushaf_layout_consistency",
            ),
```

- [ ] **Step 5: Generate the field migration only**

Temporarily comment out the two new entries in `Meta.constraints`, then run:

```bash
.venv/bin/python manage.py makemigrations content --name asset_template_fields
```

Expected: `0063_asset_template_fields.py` with two `AddField` operations and no `AddConstraint`.

- [ ] **Step 6: Write the backfill migration by hand**

Create `apps/content/migrations/0064_backfill_asset_template.py`:

```python
from django.db import migrations

TEXT_CATEGORIES = ["translation", "tafsir"]


def backfill_template(apps, schema_editor):
    """Every pre-existing translation / tafsir was ayah-keyed by construction."""
    Asset = apps.get_model("content", "Asset")
    Asset.objects.filter(category__in=TEXT_CATEGORIES, template__isnull=True).update(template="ayah")


def clear_template(apps, schema_editor):
    Asset = apps.get_model("content", "Asset")
    Asset.objects.filter(category__in=TEXT_CATEGORIES).update(template=None)


class Migration(migrations.Migration):
    dependencies = [("content", "0063_asset_template_fields")]

    operations = [migrations.RunPython(backfill_template, clear_template)]
```

- [ ] **Step 7: Generate the constraint migration**

Un-comment the two constraints from Step 4, then run:

```bash
.venv/bin/python manage.py makemigrations content --name asset_template_constraints
```

Expected: `0065_asset_template_constraints.py` with two `AddConstraint` operations, depending on `0064`.

Open it and confirm `dependencies` names `0064_backfill_asset_template`. If it names `0063`, edit it to `0064` — the constraint must not be applied before the backfill.

- [ ] **Step 8: Write the migration test**

Create `apps/content/tests/migrations/test_backfill_asset_template.py`:

```python
import importlib

from apps.core.tests.base import BaseTestCase

# The module name starts with a digit, so a plain `from ... import` is illegal.
backfill = importlib.import_module("apps.content.migrations.0064_backfill_asset_template")


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = rows
        self.updated_with = None

    def filter(self, **kwargs):
        return self

    def update(self, **kwargs):
        self.updated_with = kwargs
        return len(self.rows)


class FakeModel:
    def __init__(self, rows):
        self.objects = FakeQuerySet(rows)


class FakeApps:
    def __init__(self, model):
        self.model = model

    def get_model(self, app_label, model_name):
        return self.model


class BackfillAssetTemplateTests(BaseTestCase):
    def test_backfill_template_where_run_should_set_ayah(self):
        # Arrange
        model = FakeModel(rows=[1, 2, 3])
        apps_registry = FakeApps(model)

        # Act
        backfill.backfill_template(apps_registry, None)

        # Assert
        self.assertEqual(model.objects.updated_with, {"template": "ayah"})

    def test_clear_template_where_reversed_should_set_none(self):
        # Arrange
        model = FakeModel(rows=[1])
        apps_registry = FakeApps(model)

        # Act
        backfill.clear_template(apps_registry, None)

        # Assert
        self.assertEqual(model.objects.updated_with, {"template": None})
```

- [ ] **Step 9: Apply the migrations and run the tests**

```bash
.venv/bin/python manage.py migrate content
.venv/bin/pytest apps/content/tests/models/test_asset_template.py apps/content/tests/migrations/test_backfill_asset_template.py -v
```
Expected: all pass.

- [ ] **Step 10: Verify existing suites still pass**

Run: `.venv/bin/pytest apps/content -x -q`
Expected: pass. Any failure here means existing factories build translations/tafsirs without a template — fix by giving those factories `template=AssetTemplateChoice.AYAH`, not by weakening the constraint.

- [ ] **Step 11: Commit**

```bash
git add apps/content/models.py apps/content/migrations/006[345]_*.py \
        apps/content/tests/models/test_asset_template.py \
        apps/content/tests/migrations/test_backfill_asset_template.py
git commit -m "feat: add Asset.template and mushaf_layout with ayah backfill"
```

---
### Task 3: Unit columns on `AssetVersionEntry` and `AssetVersionChange`

**Files:**
- Modify: `apps/content/models.py`
- Create: `apps/content/migrations/0066_entry_unit_columns.py` (generated, then hand-edited)
- Create: `apps/content/tests/quran_data.py` (the `QuranDataMixin` from Global Constraints — every later Quran-dependent task imports it)
- Test: `apps/content/tests/models/test_entry_units.py`

**Interfaces:**
- Consumes: Task 2's migration chain (this depends on `0065`).
- Produces: on both `AssetVersionEntry` and `AssetVersionChange` — `sura: Sura | None`, `ayah: Ayah | None` (now nullable), `word: Word | None`, `page_no: int | None`; constraints `entry_exactly_one_unit` / `change_exactly_one_unit`; unique constraints `unique_entry_per_version_{sura,word,page}` and `unique_change_per_version_{sura,word,page}`; `apps/content/tests/quran_data.py::QuranDataMixin` with `bake_quran()`.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/models/test_entry_units.py`:

```python
from django.db import IntegrityError
from model_bakery import baker

from apps.content.models import AssetVersion, AssetVersionEntry
from apps.core.tests.base import BaseTestCase
from apps.quran.models import Ayah, Sura


class EntryUnitConstraintTests(BaseTestCase):
    # Task 3 creates the mixin; these tests bake inline so the mixin's own
    # first consumer is Task 5, after it has been reviewed.
    def test_entry_where_no_unit_is_set_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, text="x")

    def test_entry_where_two_units_are_set_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)
        ayah = baker.make(Ayah, id=1, sura=sura, number_in_sura=1, text="ayah 1")

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, sura=sura, ayah=ayah, text="x")

    def test_entry_where_only_sura_is_set_should_save(self):
        # Arrange
        version = baker.make(AssetVersion)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)

        # Act
        entry = AssetVersionEntry.objects.create(version=version, sura=sura, text="x", order=sura.id)

        # Assert
        self.assertEqual(entry.sura_id, sura.id)
        self.assertIsNone(entry.ayah_id)

    def test_entry_where_only_page_no_is_set_should_save(self):
        # Arrange
        version = baker.make(AssetVersion)

        # Act
        entry = AssetVersionEntry.objects.create(version=version, page_no=42, text="x", order=42)

        # Assert
        self.assertEqual(entry.page_no, 42)
        self.assertIsNone(entry.ayah_id)

    def test_entry_where_same_sura_twice_in_one_version_should_raise_integrity_error(self):
        # Arrange
        version = baker.make(AssetVersion)
        sura = baker.make(Sura, id=1, name="الفاتحة", transliterated_name="Al-Fatiha", ayas_count=1)
        AssetVersionEntry.objects.create(version=version, sura=sura, text="a", order=sura.id)

        # Act / Assert
        with self.assertRaises(IntegrityError):
            AssetVersionEntry.objects.create(version=version, sura=sura, text="b", order=sura.id)
```

The test DB has no Quran rows — every one of these tests bakes what it needs (see Global Constraints). Import `Sura` and `Ayah` from `apps.quran.models` and `baker` from `model_bakery`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/models/test_entry_units.py -v`
Expected: FAIL — `AssetVersionEntry` has no `sura` / `page_no` field, and the first test does not raise because `ayah` is still `NOT NULL` at a different layer.

- [ ] **Step 3: Add the columns to both models**

In `apps/content/models.py`, in `AssetVersionEntry`, replace the existing `ayah` field with the four unit fields:

```python
    sura = models.ForeignKey(
        "quran.Sura",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Canonical sura (1-114) — set only for surah-template assets",
    )
    ayah = models.ForeignKey(
        "quran.Ayah",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Canonical ayah (1-6236) — set only for ayah-template assets",
    )
    word = models.ForeignKey(
        "quran.Word",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Canonical word — set only for word-template assets",
    )
    page_no = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Page within the asset's MushafLayout — set only for page-template assets",
    )
```

Replace `AssetVersionEntry.Meta` with:

```python
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(sura__isnull=False, ayah__isnull=True, word__isnull=True, page_no__isnull=True)
                    | models.Q(sura__isnull=True, ayah__isnull=False, word__isnull=True, page_no__isnull=True)
                    | models.Q(sura__isnull=True, ayah__isnull=True, word__isnull=False, page_no__isnull=True)
                    | models.Q(sura__isnull=True, ayah__isnull=True, word__isnull=True, page_no__isnull=False)
                ),
                name="entry_exactly_one_unit",
            ),
            models.UniqueConstraint(fields=["version", "ayah"], name="unique_entry_per_version_ayah"),
            models.UniqueConstraint(fields=["version", "sura"], name="unique_entry_per_version_sura"),
            models.UniqueConstraint(fields=["version", "word"], name="unique_entry_per_version_word"),
            models.UniqueConstraint(fields=["version", "page_no"], name="unique_entry_per_version_page"),
        ]
        indexes = [
            models.Index(fields=["version", "order"]),
        ]
```

Postgres treats NULLs as distinct in a unique index, so each constraint only binds rows where its column is set. No partial-index `condition` is needed.

Update `__str__` to not assume ayah:

```python
    def __str__(self) -> str:
        return f"AssetVersionEntry(version={self.version_id}, unit={self.unit_id})"

    @property
    def unit_id(self) -> int:
        """The canonical id of whichever unit this entry is keyed to."""
        return self.sura_id or self.ayah_id or self.word_id or self.page_no
```

Apply the identical four fields to `AssetVersionChange`, and replace its `Meta` the same way, with constraint names `change_exactly_one_unit`, `unique_change_per_version_ayah`, `unique_change_per_version_sura`, `unique_change_per_version_word`, `unique_change_per_version_page`. Give `AssetVersionChange` the same `unit_id` property.

- [ ] **Step 4: Generate the migration**

Run: `.venv/bin/python manage.py makemigrations content --name entry_unit_columns`
Expected: `0066_entry_unit_columns.py` with `AlterField` on `ayah` (both models), six `AddField`, two `RemoveConstraint`, ten `AddConstraint`.

- [ ] **Step 5: Split the check-constraint validation**

Adding a `CheckConstraint` takes an `ACCESS EXCLUSIVE` lock and validates the whole table. `assetversionentry` holds up to 6,236 rows per version per language.

**Before editing, measure it:**

```bash
.venv/bin/python manage.py shell -c "from apps.content.models import AssetVersionEntry; print(AssetVersionEntry.objects.count())"
```

If the count is under ~100,000, leave the generated migration as-is and skip to Step 6 — the scan is sub-second and the split adds risk for no gain. Record the count in the commit message either way.

If it is larger, split the work across **two** migrations. The `AddConstraint`
operations for `entry_exactly_one_unit` and `change_exactly_one_unit` become a
`SeparateDatabaseAndState` in `0066` that adds them `NOT VALID`, and the
`VALIDATE CONSTRAINT` statements go in a separate `0067`.

**The second migration is not optional.** A Django migration is atomic by
default, and Postgres holds `ACCESS EXCLUSIVE` — taken by
`ADD CONSTRAINT … NOT VALID` — until the transaction commits. Put `VALIDATE`
in the same migration and it performs its full-table scan under that lock,
giving exactly the lock profile the split exists to avoid. Only a separate
migration, which is its own transaction, lets `0066` commit and release the
lock so `VALIDATE` can run under the lighter `SHARE UPDATE EXCLUSIVE` that
permits concurrent reads and writes. Do **not** reach for `atomic = False`
instead — it would achieve the lock release at the cost of per-migration
atomicity.

```python
migrations.SeparateDatabaseAndState(
    database_operations=[
        migrations.RunSQL(
            sql=(
                "ALTER TABLE content_assetversionentry "
                "ADD CONSTRAINT entry_exactly_one_unit CHECK ("
                "  (sura_id IS NOT NULL)::int + (ayah_id IS NOT NULL)::int"
                "+ (word_id IS NOT NULL)::int + (page_no IS NOT NULL)::int = 1"
                ") NOT VALID"
            ),
            reverse_sql="ALTER TABLE content_assetversionentry DROP CONSTRAINT entry_exactly_one_unit",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE content_assetversionentry VALIDATE CONSTRAINT entry_exactly_one_unit",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ],
    state_operations=[
        migrations.AddConstraint(model_name="assetversionentry", constraint=...),  # the constraint object from Step 3
    ],
)
```

Confirm the real table name first:

```bash
.venv/bin/python manage.py shell -c "from apps.content.models import AssetVersionEntry; print(AssetVersionEntry._meta.db_table)"
```

Every existing row has `ayah` set, so validation is satisfied by construction and cannot fail.

- [ ] **Step 6: Apply and run the tests**

```bash
.venv/bin/python manage.py migrate content
.venv/bin/pytest apps/content/tests/models/test_entry_units.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Run the whole content suite**

Run: `.venv/bin/pytest apps/content -x -q`
Expected: pass. Existing code reads `entry.ayah` directly in several places; those still work because ayah-template rows keep their `ayah` set. If something fails on `entry.ayah.sura` being `None`, it is reading an entry it did not create — note the location, it will be revisited in Task 6.

- [ ] **Step 8: Commit**

```bash
git add apps/content/models.py apps/content/migrations/0066_entry_unit_columns.py \
        apps/content/tests/models/test_entry_units.py
git commit -m "feat: add unit columns to asset version entries and changes"
```

---

### Task 4: Template immutability

**Files:**
- Modify: `apps/content/models.py` (`Asset.from_db`, `Asset.save`)
- Modify: `apps/content/admin.py`
- Test: `apps/content/tests/models/test_asset_template_immutability.py`

**Interfaces:**
- Consumes: `Asset.template`, `Asset.mushaf_layout` (Task 2).
- Produces: `ItqanError(error_name="asset_template_immutable", status_code=400)` raised from `Asset.save()` when `template` or `mushaf_layout_id` differs from the value loaded from the database.

This is layer 3 of the three-layer scheme. Layer 1 (absence from the `PutIn` schemas) and layer 2 (the service guard) land in Task 10, where those schemas and services are touched.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/models/test_asset_template_immutability.py`:

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class AssetTemplateImmutabilityTests(BaseTestCase):
    def test_save_where_template_changed_should_raise_itqan_error(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH
        )
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.template = AssetTemplateChoice.SURAH

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            reloaded.save()
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")

    def test_save_where_mushaf_layout_changed_should_raise_itqan_error(self):
        # Arrange
        first = baker.make(MushafLayout, name="Madani 604", page_count=604)
        second = baker.make(MushafLayout, name="Indo-Pak 611", page_count=611)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=first,
        )
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.mushaf_layout = second

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            reloaded.save()
        self.assertEqual(ctx.exception.error_name, "asset_template_immutable")

    def test_save_where_template_unchanged_should_save_other_fields(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH
        )
        reloaded = Asset.objects.get(pk=asset.pk)
        reloaded.description = "updated"

        # Act
        reloaded.save()

        # Assert
        self.assertEqual(Asset.objects.get(pk=asset.pk).description, "updated")

    def test_save_where_asset_is_new_should_not_raise(self):
        # Arrange / Act
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD
        )

        # Assert
        self.assertEqual(asset.template, AssetTemplateChoice.WORD)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/models/test_asset_template_immutability.py -v`
Expected: FAIL — the first two tests save successfully instead of raising.

- [ ] **Step 3: Implement the guard**

In `apps/content/models.py`, add to `Asset` (above the existing `save`):

```python
    @classmethod
    def from_db(cls, db, field_names, values):
        """Remember the persisted template so ``save`` can detect a mutation.

        Riding the original values on the instance avoids the extra query a
        re-read would cost on every save.
        """
        instance = super().from_db(db, field_names, values)
        instance._loaded_template = instance.template
        instance._loaded_mushaf_layout_id = instance.mushaf_layout_id
        return instance
```

At the top of the existing `Asset.save`, before the riwayah/slug logic:

```python
        if self.pk is not None and hasattr(self, "_loaded_template"):
            changed = (
                self.template != self._loaded_template
                or self.mushaf_layout_id != self._loaded_mushaf_layout_id
            )
            if changed:
                raise ItqanError(
                    error_name="asset_template_immutable",
                    message=_("An asset's template cannot be changed after creation."),
                    status_code=400,
                )
```

Add the import at the top of `apps/content/models.py`:

```python
from apps.core.ninja_utils.errors import ItqanError
```

If that import creates a circular import, move `ItqanError` to a function-local import inside `save()` instead — a model importing an API utility is the unusual direction here.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest apps/content/tests/models/test_asset_template_immutability.py -v`
Expected: 4 passed.

- [ ] **Step 5: Make the admin fields readonly**

In `apps/content/admin.py`, on the `Asset` admin class:

```python
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            readonly += ["template", "mushaf_layout"]
        return readonly
```

Register a `MushafLayout` admin in the same file:

```python
@admin.register(MushafLayout)
class MushafLayoutAdmin(admin.ModelAdmin):
    list_display = ("name", "page_count")
    search_fields = ("name",)
```

Import `MushafLayout` from `.models` at the top of the file.

- [ ] **Step 6: Localization**

One new `_()` string. Run `extendedmakemessages` as in Task 1 Step 6 and add:

| msgid | msgstr |
| --- | --- |
| `An asset's template cannot be changed after creation.` | `لا يمكن تغيير قالب المادة بعد إنشائها.` |

Verify `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null` reports 0 untranslated.

- [ ] **Step 7: Run the content suite**

Run: `.venv/bin/pytest apps/content -x -q`
Expected: pass. A failure here means some existing code path re-saves an asset after mutating `template` — find it and stop it mutating, do not weaken the guard.

- [ ] **Step 8: Commit**

```bash
git add apps/content/models.py apps/content/admin.py \
        apps/content/tests/models/test_asset_template_immutability.py \
        locale/ar/LC_MESSAGES/django.po
git commit -m "feat: enforce asset template immutability at the model layer"
```

---
## Phase 2 — Template descriptor and virtual entry enumeration (backend)

### Task 5: The `UnitSpec` descriptor

**Files:**
- Create: `apps/content/services/asset_templates.py`
- Test: `apps/content/tests/services/test_asset_templates.py`

**Interfaces:**
- Consumes: `AssetTemplateChoice`, `Asset.template`, `Asset.mushaf_layout` (Tasks 1-2).
- Produces:
  - `unit_spec_for(asset: Asset) -> UnitSpec` — the descriptor for an asset's template; raises `ItqanError("asset_template_missing", 400)` if the asset has none.
  - `UnitSpec.field: str` — `"sura"` / `"ayah"` / `"word"` / `"page_no"`.
  - `UnitSpec.fk_field: str | None` — the same, but `None` for `page`, which is not an FK.
  - `UnitSpec.total(asset: Asset) -> int`
  - `UnitSpec.units(asset: Asset, *, sura: int | None = None) -> Sequence[UnitRow]`
  - `UnitRow` — a dataclass with `unit_id: int`, `label: str`, `reference_text: str`, `sura: int | None`, `aya: int | None`, `order: int`.

This module is the **only** place the four-way branch may live. Later tasks consult it rather than branching themselves.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/services/test_asset_templates.py`:

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.asset_templates import unit_spec_for
from apps.core.tests.base import BaseTestCase


class UnitSpecTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_total_where_template_is_surah_should_return_114(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert — 2 suras baked by bake_quran, not the canonical 114
        self.assertEqual(total, 2)

    def test_total_where_template_is_ayah_should_return_6236(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert — 3 ayahs baked by bake_quran, not the canonical 6236
        self.assertEqual(total, 3)

    def test_total_where_template_is_page_should_return_layout_page_count(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        total = unit_spec_for(asset).total(asset)

        # Assert
        self.assertEqual(total, 604)

    def test_units_where_template_is_surah_should_label_with_number_and_name(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH)

        # Act
        first = unit_spec_for(asset).units(asset)[0]

        # Assert
        self.assertEqual(first.unit_id, 1)
        self.assertEqual(first.label, "1. Al-Fatiha")
        self.assertEqual(first.sura, 1)
        self.assertIsNone(first.aya)

    def test_units_where_template_is_page_should_label_with_page_number(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Small", page_count=3)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        rows = unit_spec_for(asset).units(asset)

        # Assert
        self.assertEqual([row.unit_id for row in rows], [1, 2, 3])
        self.assertEqual(rows[0].label, "Page 1")
        self.assertEqual(rows[0].reference_text, "")

    def test_units_where_word_template_filtered_by_sura_should_only_return_that_sura(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD)

        # Act
        rows = unit_spec_for(asset).units(asset, sura=1)

        # Assert
        self.assertTrue(rows)
        self.assertTrue(all(row.sura == 1 for row in rows))

    def test_unit_spec_for_where_asset_has_no_template_should_raise(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.FONT, template=None)

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            unit_spec_for(asset)
        self.assertEqual(ctx.exception.error_name, "asset_template_missing")
```

Add `from apps.core.ninja_utils.errors import ItqanError` to the test's imports.

Every test in this class calls `self.bake_quran()` (see Global Constraints) in its Arrange step before making an asset. The label `"1. Al-Fatiha"` matches the `transliterated_name` that helper bakes, so the assertion is self-contained — there is no fixture to consult.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_templates.py -v`
Expected: FAIL — `ModuleNotFoundError: apps.content.services.asset_templates`.

- [ ] **Step 3: Implement the descriptor**

Create `apps/content/services/asset_templates.py`:

```python
"""The single place the surah / ayah / word / page branch lives.

Every consumer — the entries endpoint, the patch path, the diff pipeline, the
importer and the CSV export — asks this module which column an asset's entries
are keyed to and what its canonical unit set is, rather than branching on
``Asset.template`` itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from django.utils.translation import gettext as _

from apps.content.models import Asset, AssetTemplateChoice
from apps.core.ninja_utils.errors import ItqanError
from apps.quran.models import Ayah, Sura, Word


@dataclass(frozen=True)
class UnitRow:
    """One canonical unit of a template, before any stored text is overlaid."""

    unit_id: int
    label: str
    reference_text: str
    sura: int | None
    aya: int | None
    order: int


@dataclass(frozen=True)
class UnitSpec:
    template: AssetTemplateChoice
    field: str
    fk_field: str | None

    def total(self, asset: Asset) -> int:
        if self.template == AssetTemplateChoice.SURAH:
            return Sura.objects.count()
        if self.template == AssetTemplateChoice.AYAH:
            return Ayah.objects.count()
        if self.template == AssetTemplateChoice.WORD:
            return Word.objects.count()
        return asset.mushaf_layout.page_count

    def units(self, asset: Asset, *, sura: int | None = None) -> Sequence[UnitRow]:
        if self.template == AssetTemplateChoice.SURAH:
            qs = Sura.objects.all()
            if sura is not None:
                qs = qs.filter(id=sura)
            return [
                UnitRow(
                    unit_id=row.id,
                    label=f"{row.id}. {row.transliterated_name}",
                    reference_text=row.name,
                    sura=row.id,
                    aya=None,
                    order=row.id,
                )
                for row in qs
            ]

        if self.template == AssetTemplateChoice.AYAH:
            qs = Ayah.objects.select_related("sura")
            if sura is not None:
                qs = qs.filter(sura_id=sura)
            return [
                UnitRow(
                    unit_id=row.id,
                    label=f"{row.sura_id}:{row.number_in_sura}",
                    reference_text=row.text,
                    sura=row.sura_id,
                    aya=row.number_in_sura,
                    order=row.id,
                )
                for row in qs
            ]

        if self.template == AssetTemplateChoice.WORD:
            qs = Word.objects.select_related("ayah")
            if sura is not None:
                qs = qs.filter(sura_id=sura)
            return [
                UnitRow(
                    unit_id=row.id,
                    label=f"{row.sura_id}:{row.ayah.number_in_sura}:{row.position_in_ayah}",
                    reference_text=row.text,
                    sura=row.sura_id,
                    aya=row.ayah.number_in_sura,
                    order=row.id,
                )
                for row in qs
            ]

        # page: generated, there is no page table
        page_count = asset.mushaf_layout.page_count
        if sura is not None:
            return []
        return [
            UnitRow(
                unit_id=page,
                label=_("Page {number}").format(number=page),
                reference_text="",
                sura=None,
                aya=None,
                order=page,
            )
            for page in range(1, page_count + 1)
        ]


_SPECS: dict[str, UnitSpec] = {
    AssetTemplateChoice.SURAH: UnitSpec(AssetTemplateChoice.SURAH, "sura", "sura"),
    AssetTemplateChoice.AYAH: UnitSpec(AssetTemplateChoice.AYAH, "ayah", "ayah"),
    AssetTemplateChoice.WORD: UnitSpec(AssetTemplateChoice.WORD, "word", "word"),
    AssetTemplateChoice.PAGE: UnitSpec(AssetTemplateChoice.PAGE, "page_no", None),
}


def unit_spec_for(asset: Asset) -> UnitSpec:
    """The descriptor for an asset's template."""
    spec = _SPECS.get(asset.template)
    if spec is None:
        raise ItqanError(
            error_name="asset_template_missing",
            message=_("This asset has no content template."),
            status_code=400,
        )
    return spec
```

`units()` for the word template materialises 77,431 rows. Task 6 slices before calling it; nothing else may call it unsliced.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_templates.py -v`
Expected: 7 passed.

- [ ] **Step 5: Add slicing support**

The word template's `units()` is too large to build in full on every request. Add a `units_page` method to `UnitSpec` that pushes the slice into the query:

```python
    def units_page(
        self, asset: Asset, *, offset: int, limit: int, sura: int | None = None
    ) -> tuple[Sequence[UnitRow], int]:
        """One page of canonical units, plus the total count for that filter.

        The slice is applied to the queryset (or the page range) before any
        ``UnitRow`` is built, so a word-template request never materialises
        77,431 objects.
        """
```

Implement it by refactoring `units()` into a `_queryset(asset, sura)` helper returning the queryset (or, for `page`, a `range`), then:

```python
        source = self._queryset(asset, sura)
        # `range` also has a `.count()`, but with different semantics
        # (`range.count(value)`), so discriminate on the type, not the attribute.
        total = len(source) if isinstance(source, range) else source.count()
        window = source[offset : offset + limit]
        return [self._to_row(item) for item in window], total
```

Move the per-template `UnitRow` construction into `_to_row`, which dispatches on
`self.template` exactly as `units()` does today. Keep `units()` as a thin wrapper:

```python
    def units(self, asset: Asset, *, sura: int | None = None) -> Sequence[UnitRow]:
        rows, _total = self.units_page(asset, offset=0, limit=self.total(asset), sura=sura)
        return rows
```

- [ ] **Step 6: Test the slicing**

Append to `apps/content/tests/services/test_asset_templates.py`:

```python
    def test_units_page_where_offset_given_should_return_that_window(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.AYAH)

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=1, limit=5)

        # Assert — 3 ayahs baked; offset 1 limit 5 yields ids 2 and 3
        self.assertEqual(total, 3)
        self.assertEqual([row.unit_id for row in rows], [2, 3])

    def test_units_page_where_page_template_should_window_the_range(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        rows, total = unit_spec_for(asset).units_page(asset, offset=600, limit=10)

        # Assert
        self.assertEqual(total, 604)
        self.assertEqual([row.unit_id for row in rows], [601, 602, 603, 604])
```

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_templates.py -v`
Expected: 9 passed.

- [ ] **Step 7: Localization**

Two new `_()` strings. Run `extendedmakemessages` and add:

| msgid | msgstr |
| --- | --- |
| `Page {number}` | `صفحة {number}` |
| `This asset has no content template.` | `هذه المادة ليس لها قالب محتوى.` |

Verify 0 untranslated.

- [ ] **Step 8: Commit**

```bash
git add apps/content/services/asset_templates.py \
        apps/content/tests/services/test_asset_templates.py \
        locale/ar/LC_MESSAGES/django.po
git commit -m "feat: add UnitSpec template descriptor"
```

---
### Task 6: Virtual entry enumeration

**Files:**
- Modify: `apps/content/repositories/asset_content.py`
- Modify: `apps/content/services/asset_content.py`
- Modify: `apps/content/api/portal/asset_content.py`
- Test: `apps/content/tests/portal/test_asset_content_templates.py`

**Interfaces:**
- Consumes: `unit_spec_for`, `UnitSpec.units_page`, `UnitRow` (Task 5).
- Produces:
  - `AssetContentRepository.entry_text_map(version: AssetVersion, spec: UnitSpec, unit_ids: list[int]) -> dict[int, str]`
  - `AssetContentService.get_entries_page(slug, category, version_id, *, offset, limit, sura=None, publisher_q=None) -> tuple[list[dict], int]`
  - `EntryOut` with fields `unit_type`, `unit_id`, `label`, `reference_text`, `sura`, `aya`, `text`, `source_text`, `order`.

This replaces the paginated-stored-entries behaviour. A fresh surah asset must return 114 rows while writing zero rows.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/portal/test_asset_content_templates.py`:

```python
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    MushafLayout,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase


class EntriesEnumerationTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()  # see Global Constraints

    def _draft_for(self, template, layout=None):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        return asset, version

    def test_list_entries_where_surah_asset_is_empty_should_return_114_rows(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.get(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(len(body["results"]), 2)
        self.assertTrue(all(item["text"] == "" for item in body["results"]))
        self.assertEqual(AssetVersionEntry.objects.filter(version=version).count(), 0)

    def test_list_entries_where_surah_asset_has_one_entry_should_overlay_its_text(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)
        AssetVersionEntry.objects.create(version=version, sura_id=self.sura2.id, text="content", order=2)

        # Act
        response = self.client.get(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/?page_size=200"
        )

        # Assert
        items = {item["unit_id"]: item["text"] for item in response.json()["results"]}
        self.assertEqual(items[self.sura2.id], "content")
        self.assertEqual(items[self.sura1.id], "")

    def test_list_entries_where_page_asset_should_return_layout_page_count_rows(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        asset, version = self._draft_for(AssetTemplateChoice.PAGE, layout=layout)

        # Act
        response = self.client.get(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/?page_size=5"
        )

        # Assert
        body = response.json()
        self.assertEqual(body["count"], 604)
        self.assertEqual([item["unit_id"] for item in body["results"]], [1, 2, 3, 4, 5])
        self.assertEqual(body["results"][0]["unit_type"], "page")

    def test_list_entries_where_word_asset_filtered_by_sura_should_narrow_the_count(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.WORD)

        # Act
        response = self.client.get(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/?page_size=10&sura=1"
        )

        # Assert
        body = response.json()
        # 2 words baked, both in sura 1
        self.assertEqual(body["count"], 2)
        self.assertTrue(all(item["sura"] == 1 for item in body["results"]))

    def test_list_entries_where_ayah_asset_should_keep_returning_6236_rows(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.get(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/?page_size=1"
        )

        # Assert — 3 ayahs baked, not the canonical 6236
        body = response.json()
        self.assertEqual(body["count"], 3)
        self.assertEqual(body["results"][0]["label"], "1:1")
```

The envelope above matches `apps.core.ninja_utils.paginations.NinjaPagination`,
the project default: `{"results": [...], "count": N}`, driven by `page` and
`page_size` query params (`page_size` defaults to 20 and is capped at 1000 by
`MAX_PAGE_SIZE`). The new endpoint must keep that exact envelope — the frontend
service already depends on it.

Check how `self.authenticate_user` takes permissions in this codebase:

```bash
sed -n '1,80p' apps/core/tests/base.py
```

Adjust the calls to match its real signature.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_content_templates.py -v`
Expected: FAIL — responses carry `ayah_id` and the surah asset returns 0 rows.

- [ ] **Step 3: Add the text-map repository method**

In `apps/content/repositories/asset_content.py`, add to `AssetContentRepository`:

```python
    def entry_text_map(self, version: AssetVersion, spec: UnitSpec, unit_ids: list[int]) -> dict[int, str]:
        """Stored text for the given units of one version, keyed by unit id.

        Only the units on the requested page are fetched, so a word-template
        request reads at most ``limit`` rows rather than the whole version.
        """
        lookup = {f"{spec.field}__in": unit_ids}
        rows = version.entries.filter(**lookup).values_list(spec.field, "text")
        return {unit_id: text for unit_id, text in rows}
```

For the FK templates, `values_list("sura", ...)` yields the FK's id, which is what the map needs. Import `UnitSpec` from `apps.content.services.asset_templates`.

- [ ] **Step 4: Add the service method**

In `apps/content/services/asset_content.py`, add to `AssetContentService`:

```python
    def get_entries_page(
        self,
        slug: str,
        category: CategoryChoice,
        version_id: int,
        *,
        offset: int,
        limit: int,
        sura: int | None = None,
        publisher_q: Q | None = None,
    ) -> tuple[list[dict], int]:
        """One page of the template's canonical units with stored text overlaid.

        Units the version has no row for come back with empty text. Nothing is
        written: a freshly created asset shows its full unit set without any
        entry rows existing.
        """
        asset = self._get_asset_or_404(slug, category, publisher_q=publisher_q)
        version = self.repo.get_version(asset, version_id)
        if version is None:
            raise ItqanError(
                error_name="version_not_found",
                message=_("Version with id {id} not found.").format(id=version_id),
                status_code=404,
            )

        spec = unit_spec_for(asset)
        units, total = spec.units_page(asset, offset=offset, limit=limit, sura=sura)
        text_by_unit = self.repo.entry_text_map(version, spec, [unit.unit_id for unit in units])

        rows = [
            {
                "unit_type": asset.template,
                "unit_id": unit.unit_id,
                "label": unit.label,
                "reference_text": unit.reference_text,
                "sura": unit.sura,
                "aya": unit.aya,
                "text": text_by_unit.get(unit.unit_id, ""),
                "source_text": None,
                "order": unit.order,
            }
            for unit in units
        ]
        return rows, total
```

Import `unit_spec_for` from `apps.content.services.asset_templates`.

- [ ] **Step 5: Reshape the endpoint**

In `apps/content/api/portal/asset_content.py`, replace `EntryOut` with:

```python
class EntryOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    reference_text: str
    sura: int | None = None
    aya: int | None = None
    text: str
    source_text: str | None = None
    order: int
```

Replace the `list_entries` view. It no longer uses `@paginate`, because the total comes from the unit set rather than a queryset:

```python
class EntriesPageOut(Schema):
    """Mirrors NinjaPagination.Output so the envelope is unchanged."""

    results: list[EntryOut]
    count: int


@router.get(
    "content/{category}/{slug}/versions/{version_id}/entries/",
    response={
        200: EntriesPageOut,
        400: NinjaErrorResponse[Literal["asset_template_missing"]],
        404: NinjaErrorResponse[Literal["translation_not_found"]]
        | NinjaErrorResponse[Literal["tafsir_not_found"]]
        | NinjaErrorResponse[Literal["version_not_found"]]
        | NinjaErrorResponse[Literal["unsupported_content_category"]],
    },
)
def list_entries(
    request: Request,
    category: str,
    slug: str,
    version_id: int,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    sura: int | None = None,
):
    resolved = _resolve_for_version(category, request, slug, version_id, write=False)
    service = AssetContentService()
    page_size = min(page_size, MAX_PAGE_SIZE)
    rows, count = service.get_entries_page(
        slug,
        resolved,
        version_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        sura=sura,
        publisher_q=request.publisher_q(),
    )
    return {"results": rows, "count": count}
```

Import `DEFAULT_PAGE_SIZE` and `MAX_PAGE_SIZE` from `apps.core.ninja_utils.paginations`.

Import `AssetTemplateChoice` from `apps.content.models`.

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_content_templates.py -v`
Expected: 5 passed.

- [ ] **Step 7: Fix the fallout in existing tests**

Run: `.venv/bin/pytest apps/content/tests/portal -q`
Expected: failures in the existing asset-content tests, which assert `ayah_id` / `surah_name` / `uthmani`.

Update each to the new field names: `ayah_id` → `unit_id`, `surah_name` → (removed; the surah name now rides in `reference_text` only for the surah template, so assert on `label` instead), `uthmani` → `reference_text`. Do not reintroduce the old names as aliases.

- [ ] **Step 8: Run the whole content suite**

Run: `.venv/bin/pytest apps/content -q`
Expected: pass.

- [ ] **Step 9: Commit**

```bash
git add apps/content/repositories/asset_content.py \
        apps/content/services/asset_content.py \
        apps/content/api/portal/asset_content.py \
        apps/content/tests/
git commit -m "feat: enumerate entries from the template unit set"
```

---

### Task 7: Unit-aware writes, diff and draft seeding

**Files:**
- Modify: `apps/content/repositories/asset_content.py`
- Modify: `apps/content/services/asset_content.py`
- Modify: `apps/content/api/portal/asset_content.py`
- Test: `apps/content/tests/portal/test_asset_content_template_writes.py`

**Interfaces:**
- Consumes: `unit_spec_for`, `UnitSpec.field` (Task 5); `get_entries_page` (Task 6).
- Produces: `EntryPatchRow` with field `unit_id: int` (replacing `ayah_id`); `ChangeOut` reshaped to match `EntryOut`; `AssetContentRepository.upsert_entries` writing `spec.field`.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/portal/test_asset_content_template_writes.py`:

```python
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
    StatusChoice,
    VersionStateChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase


class EntryWriteTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()  # see Global Constraints

    def _draft_for(self, template):
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=template,
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT)
        return asset, version

    def test_patch_entries_where_surah_template_should_write_the_sura_column(self):
        # sura id 2 is baked by bake_quran; 999 below is deliberately absent
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_UPDATE_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 2, "text": "surah two"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.sura_id, 2)
        self.assertIsNone(entry.ayah_id)
        self.assertEqual(entry.text, "surah two")

    def test_patch_entries_where_page_template_should_write_the_page_no_column(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_UPDATE_TRANSLATION])
        layout = baker.make("content.MushafLayout", name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset, state=VersionStateChoice.DRAFT)

        # Act
        response = self.client.patch(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 7, "text": "page seven"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.page_no, 7)

    def test_patch_entries_where_unit_out_of_range_should_return_400(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_UPDATE_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.SURAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 999, "text": "nope"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "unit_not_in_template")

    def test_patch_entries_where_ayah_template_should_still_write_the_ayah_column(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_UPDATE_TRANSLATION])
        asset, version = self._draft_for(AssetTemplateChoice.AYAH)

        # Act
        response = self.client.patch(
            f"/portal/content/translation/{asset.slug}/versions/{version.id}/entries/",
            data={"rows": [{"unit_id": 1, "text": "bismillah"}]},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 200)
        entry = AssetVersionEntry.objects.get(version=version)
        self.assertEqual(entry.ayah_id, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_content_template_writes.py -v`
Expected: FAIL — `EntryPatchRow` rejects `unit_id`.

- [ ] **Step 3: Reshape the patch input**

In `apps/content/api/portal/asset_content.py`:

```python
class EntryPatchRow(Schema):
    unit_id: int
    text: str = ""
```

Add `unit_not_in_template` to `patch_entries`' documented responses:

```python
        400: NinjaErrorResponse[Literal["version_not_editable"]]
        | NinjaErrorResponse[Literal["unit_not_in_template"]]
        | NinjaErrorResponse[Literal["asset_template_missing"]],
```

Change the view to return the reshaped page rather than raw entries:

```python
def patch_entries(request: Request, category: str, slug: str, version_id: int, data: EntriesPatchIn):
    resolved = _resolve_for_version(category, request, slug, version_id, write=True)
    service = AssetContentService()
    rows = [row.model_dump() for row in data.rows]
    return service.upsert_entries(slug, resolved, version_id, rows, publisher_q=request.publisher_q())
```

with `response={200: list[EntryOut], ...}` and `upsert_entries` returning dicts in `EntryOut` shape.

- [ ] **Step 4: Make the write path unit-aware**

In `apps/content/repositories/asset_content.py`, change `upsert_entries` to take the spec and key on its field:

```python
    def upsert_entries(
        self, version: AssetVersion, spec: UnitSpec, rows: list[dict[str, object]]
    ) -> list[AssetVersionEntry]:
        """Create or update one entry per row, keyed to the template's unit column."""
        unit_ids = [int(row["unit_id"]) for row in rows]
        existing = {
            getattr(entry, f"{spec.field}_id" if spec.fk_field else spec.field): entry
            for entry in version.entries.filter(**{f"{spec.field}__in": unit_ids})
        }
        ...
```

Build new rows with `AssetVersionEntry(version=version, **{spec.field + ("_id" if spec.fk_field else ""): unit_id}, text=text, order=unit_id)`.

Keep the existing `bulk_create` / `bulk_update` batching at `batch_size=1000`.

- [ ] **Step 5: Validate the unit against the template**

In `apps/content/services/asset_content.py`, in `upsert_entries`, before writing:

```python
        candidates = [int(row["unit_id"]) for row in rows]
        valid_ids = spec.valid_unit_ids(asset, candidates)
        unknown = [unit_id for unit_id in candidates if unit_id not in valid_ids]
        if unknown:
            raise ItqanError(
                error_name="unit_not_in_template",
                message=_("Units {units} are not part of this asset's template.").format(
                    units=", ".join(str(unit) for unit in unknown[:10])
                ),
                status_code=400,
            )
```

The check must never call `spec.units(asset)` — for the word template that would
build 77,431 rows on every patch. `valid_unit_ids` bounds the query by the
candidates instead. Add it to `UnitSpec`:

```python
    def valid_unit_ids(self, asset: Asset, candidates: list[int]) -> set[int]:
        """Which of ``candidates`` are real units of this template."""
        if self.template == AssetTemplateChoice.PAGE:
            return {c for c in candidates if 1 <= c <= asset.mushaf_layout.page_count}
        model = {"sura": Sura, "ayah": Ayah, "word": Word}[self.field]
        return set(model.objects.filter(id__in=candidates).values_list("id", flat=True))
```

- [ ] **Step 6: Reshape `ChangeOut` and the diff pipeline**

In `apps/content/api/portal/asset_content.py`:

```python
class ChangeOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str
    change_type: str
    old_text: str
    new_text: str
```

In `apps/content/repositories/asset_content.py`, `_record_changes` and `_change_to_dict` currently take an `ayah`. Change them to take a `unit_id` plus the spec, and write the change row with `**{spec.field + ("_id" if spec.fk_field else ""): unit_id}`. `_entries_map` and `_order_map` key on `spec.field` rather than `ayah_id`.

- [ ] **Step 7: Skip mushaf coverage for non-ayah templates**

`ensure_mushaf_coverage` seeds a translation draft with one row per mushaf ayah. That is meaningful only for the ayah template — and with Task 6's virtual enumeration it is no longer needed for display at all. In `AssetContentService.get_or_create_draft`, guard the two `ensure_mushaf_coverage` calls:

```python
                if mushaf is not None and asset.template == AssetTemplateChoice.AYAH:
                    self.repo.ensure_mushaf_coverage(existing, mushaf)
```

Do the same at the `create_draft_seeded_from` call site, passing `mushaf_version=None` for non-ayah templates.

- [ ] **Step 8: Run the tests**

```bash
.venv/bin/pytest apps/content/tests/portal/test_asset_content_template_writes.py -v
.venv/bin/pytest apps/content -q
```
Expected: both pass. Existing diff/publish tests asserting `ayah_id` in change payloads need updating to `unit_id`.

- [ ] **Step 9: Localization**

Two new `_()` strings:

| msgid | msgstr |
| --- | --- |
| `Units {units} are not part of this asset's template.` | `الوحدات {units} ليست جزءًا من قالب هذه المادة.` |

Run `extendedmakemessages`, fill it in, verify 0 untranslated.

- [ ] **Step 10: Commit**

```bash
git add apps/content/ locale/ar/LC_MESSAGES/django.po
git commit -m "feat: make entry writes and diffs template-aware"
```

---
### Task 7A: Template-aware review surface

**Files:**
- Modify: `apps/content/api/portal/asset_review.py`
- Modify: `apps/content/repositories/asset_review.py`
- Test: `apps/content/tests/portal/test_asset_review_templates.py`

**Interfaces:**
- Consumes: the unit columns on `AssetVersionChange` (Task 3); `unit_spec_for` (Task 5).
- Produces: `ReviewChangeOut` with `unit_type`, `unit_id` and `label` in place of `sura` / `aya` / `surah_name`.

`ReviewChangeOut` currently resolves `obj.ayah.sura_id`, `obj.ayah.number_in_sura` and `obj.ayah.sura.name`. With `ayah` nullable, a surah, word or page change row makes every one of those raise `AttributeError: 'NoneType' object has no attribute 'sura_id'` — a 500 on the review page. This task closes that.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/portal/test_asset_review_templates.py`:

```python
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionChange,
    CategoryChoice,
    ChangeTypeChoice,
    StatusChoice,
)
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase


class ReviewTemplateTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_review_changes_where_surah_template_should_not_raise_and_should_label_the_unit(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_REVIEW_CONTENT])
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.SURAH,
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionChange.objects.create(
            version=version,
            sura_id=2,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="cow",
            order=2,
        )

        # Act
        response = self.client.get(f"/portal/review/translation/{asset.slug}/changes/")

        # Assert
        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual(row["unit_type"], "surah")
        self.assertEqual(row["unit_id"], 2)
        self.assertEqual(row["label"], "2. Al-Baqara")  # transliterated_name baked by bake_quran

    def test_review_changes_where_ayah_template_should_keep_the_colon_label(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_REVIEW_CONTENT])
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            status=StatusChoice.READY,
            template=AssetTemplateChoice.AYAH,
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionChange.objects.create(
            version=version,
            ayah_id=1,
            change_type=ChangeTypeChoice.ADDED,
            old_text="",
            new_text="bismillah",
            order=1,
        )

        # Act
        response = self.client.get(f"/portal/review/translation/{asset.slug}/changes/")

        # Assert
        row = response.json()["results"][0]
        self.assertEqual(row["label"], "1:1")
        self.assertEqual(row["unit_id"], 1)
```

`bake_quran()` bakes sura 2 with `transliterated_name="Al-Baqara"`, so `"2. Al-Baqara"` is self-contained. Confirm the real review endpoint path before asserting it:

```bash
grep -n "@router" apps/content/api/portal/asset_review.py
```

Use the path that prints.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_review_templates.py -v`
Expected: FAIL — the surah case raises `AttributeError` on `obj.ayah.sura_id` (surfacing as a 500); the ayah case fails on the missing `label` field.

- [ ] **Step 3: Reshape `ReviewChangeOut`**

Replace the `sura` / `aya` / `surah_name` fields and their three resolvers with:

```python
    unit_type: AssetTemplateChoice
    unit_id: int
    label: str

    @staticmethod
    def resolve_unit_type(obj: AssetVersionChange) -> str:
        return obj.version.asset.template

    @staticmethod
    def resolve_unit_id(obj: AssetVersionChange) -> int:
        return obj.unit_id

    @staticmethod
    def resolve_label(obj: AssetVersionChange) -> str:
        """The unit's display reference, matching the editor's EntryOut.label."""
        if obj.sura_id is not None:
            return f"{obj.sura_id}. {obj.sura.transliterated_name}"
        if obj.ayah_id is not None:
            return f"{obj.ayah.sura_id}:{obj.ayah.number_in_sura}"
        if obj.word_id is not None:
            return f"{obj.word.sura_id}:{obj.word.ayah.number_in_sura}:{obj.word.position_in_ayah}"
        return _("Page {number}").format(number=obj.page_no)
```

`obj.unit_id` is the property added to `AssetVersionChange` in Task 3.

Import `AssetTemplateChoice` from `apps.content.models` and `gettext as _` from `django.utils.translation`. The `Page {number}` msgid was already translated in Task 5 — reuse it, do not add a second catalog entry.

- [ ] **Step 4: Widen the review repository's `select_related`**

In `apps/content/repositories/asset_review.py`, the changes queryset selects `ayah` and `ayah__sura`. Extend it so the other three units are fetched in the same query rather than one query per row:

```python
            .select_related("sura", "ayah__sura", "word__ayah", "word__sura", "version__asset")
```

Keep whatever else that `select_related` already names. `page_no` is a plain column and needs nothing.

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/pytest apps/content/tests/portal/test_asset_review_templates.py -v
.venv/bin/pytest apps/content -q
```
Expected: both pass. Existing review tests asserting `sura` / `aya` / `surah_name` need updating to `unit_id` / `label`.

- [ ] **Step 6: Commit**

```bash
git add apps/content/api/portal/asset_review.py \
        apps/content/repositories/asset_review.py \
        apps/content/tests/
git commit -m "feat: make the review surface template-aware"
```

---

## Phase 3 — Layout CRUD and asset creation (backend)

### Task 8: `MushafLayout` permissions, repository and service

**Files:**
- Modify: `apps/core/permissions.py`
- Modify: `apps/core/ninja_utils/tags.py`
- Create: `apps/content/repositories/mushaf_layout.py`
- Create: `apps/content/services/mushaf_layout.py`
- Test: `apps/content/tests/services/test_mushaf_layout_service.py`

**Interfaces:**
- Consumes: `MushafLayout` (Task 1).
- Produces:
  - `PermissionChoice.PORTAL_{READ,CREATE,UPDATE,DELETE}_MUSHAF_LAYOUT`
  - `NinjaTag.MUSHAF_LAYOUTS`
  - `MushafLayoutRepository.create(...) / update(...) / delete(...)`
  - `MushafLayoutService.create(name_ar, name_en, page_count) -> MushafLayout`
  - `MushafLayoutService.update(layout_id, **fields) -> MushafLayout`
  - `MushafLayoutService.delete(layout_id) -> None`, raising `ItqanError("mushaf_layout_in_use", 400)` when assets reference it.

- [ ] **Step 1: Add the permissions**

In `apps/core/permissions.py`, after the Mushafs block:

```python
    # Mushaf Layouts
    PORTAL_READ_MUSHAF_LAYOUT = "portal_read_mushaf_layout", _("Portal - View Mushaf Layouts")
    PORTAL_CREATE_MUSHAF_LAYOUT = "portal_create_mushaf_layout", _("Portal - Create Mushaf Layouts")
    PORTAL_UPDATE_MUSHAF_LAYOUT = "portal_update_mushaf_layout", _("Portal - Update Mushaf Layouts")
    PORTAL_DELETE_MUSHAF_LAYOUT = "portal_delete_mushaf_layout", _("Portal - Delete Mushaf Layouts")
```

Add implications to `PERMISSION_IMPLICATIONS`, following the reciter block's shape exactly:

```python
    PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT, PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT}
    ),
    PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT: frozenset(
        {PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT, PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT}
    ),
    PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT: frozenset(
        {
            PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT,
            PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT,
            PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT,
        }
    ),
```

New `PermissionChoice` members are synced into `auth.Permission` rows on `post_migrate` and granted to the `ITQAN_INTERNAL_GROUP` automatically (see `apps/publishers/apps.py::_seed_publisher_member_groups`, which seeds that group with `PermissionChoice.values`). No fixture is needed.

In `apps/core/ninja_utils/tags.py`, add `MUSHAF_LAYOUTS = "Mushaf Layouts"` after `MUSHAFS`.

- [ ] **Step 2: Write the failing test**

Create `apps/content/tests/services/test_mushaf_layout_service.py`:

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.mushaf_layout import MushafLayoutService
from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase


class MushafLayoutServiceTests(BaseTestCase):
    def test_create_where_valid_should_persist_the_layout(self):
        # Arrange
        service = MushafLayoutService()

        # Act
        layout = service.create(name_ar="المدني ٦٠٤", name_en="Madani 604", page_count=604)

        # Assert
        self.assertEqual(MushafLayout.objects.get(pk=layout.pk).page_count, 604)

    def test_delete_where_an_asset_uses_the_layout_should_raise_in_use(self):
        # Arrange
        service = MushafLayoutService()
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.delete(layout.pk)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_in_use")

    def test_delete_where_unused_should_remove_the_layout(self):
        # Arrange
        service = MushafLayoutService()
        layout = baker.make(MushafLayout, name="Unused", page_count=10)

        # Act
        service.delete(layout.pk)

        # Assert
        self.assertFalse(MushafLayout.objects.filter(pk=layout.pk).exists())

    def test_update_where_layout_missing_should_raise_not_found(self):
        # Arrange
        service = MushafLayoutService()

        # Act / Assert
        with self.assertRaises(ItqanError) as ctx:
            service.update(999999, page_count=5)
        self.assertEqual(ctx.exception.error_name, "mushaf_layout_not_found")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/services/test_mushaf_layout_service.py -v`
Expected: FAIL — `ModuleNotFoundError: apps.content.services.mushaf_layout`.

- [ ] **Step 4: Write the repository**

Create `apps/content/repositories/mushaf_layout.py`:

```python
"""ORM access for MushafLayout writes."""

from __future__ import annotations

from apps.content.models import MushafLayout


class MushafLayoutRepository:
    def __init__(self) -> None:
        self.model = MushafLayout

    def get(self, layout_id: int) -> MushafLayout | None:
        return self.model.objects.filter(pk=layout_id).first()

    def create(self, **fields) -> MushafLayout:
        return self.model.objects.create(**fields)

    def update(self, layout: MushafLayout, **fields) -> MushafLayout:
        for name, value in fields.items():
            setattr(layout, name, value)
        layout.save(update_fields=[*fields.keys(), "updated_at"])
        return layout

    def delete(self, layout: MushafLayout) -> None:
        layout.delete()

    def is_in_use(self, layout: MushafLayout) -> bool:
        return layout.assets.exists()
```

- [ ] **Step 5: Write the service**

Create `apps/content/services/mushaf_layout.py`:

```python
"""Business rules for mushaf layouts (pagination referenced by page-based assets)."""

from __future__ import annotations

from django.utils.translation import gettext as _

from apps.content.models import MushafLayout
from apps.content.repositories.mushaf_layout import MushafLayoutRepository
from apps.core.ninja_utils.errors import ItqanError


class MushafLayoutService:
    def __init__(self, repo: MushafLayoutRepository | None = None) -> None:
        self.repo = repo or MushafLayoutRepository()

    def get_or_404(self, layout_id: int) -> MushafLayout:
        layout = self.repo.get(layout_id)
        if layout is None:
            raise ItqanError(
                error_name="mushaf_layout_not_found",
                message=_("Mushaf layout with id {id} not found.").format(id=layout_id),
                status_code=404,
            )
        return layout

    def create(self, *, name_ar: str | None, name_en: str | None, page_count: int) -> MushafLayout:
        return self.repo.create(name_ar=name_ar, name_en=name_en, page_count=page_count)

    def update(self, layout_id: int, **fields) -> MushafLayout:
        layout = self.get_or_404(layout_id)
        return self.repo.update(layout, **fields)

    def delete(self, layout_id: int) -> None:
        """Refuse to delete a layout any asset still points at.

        The FK is PROTECT, so the ORM would raise anyway — this turns that into
        a documented 400 instead of a 500.
        """
        layout = self.get_or_404(layout_id)
        if self.repo.is_in_use(layout):
            raise ItqanError(
                error_name="mushaf_layout_in_use",
                message=_("This layout is used by one or more assets and cannot be deleted."),
                status_code=400,
            )
        self.repo.delete(layout)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest apps/content/tests/services/test_mushaf_layout_service.py -v`
Expected: 4 passed.

- [ ] **Step 7: Localization**

Six new `_()` strings (four permission labels plus two error messages):

| msgid | msgstr |
| --- | --- |
| `Portal - View Mushaf Layouts` | `البوابة - عرض تخطيطات المصاحف` |
| `Portal - Create Mushaf Layouts` | `البوابة - إنشاء تخطيطات المصاحف` |
| `Portal - Update Mushaf Layouts` | `البوابة - تعديل تخطيطات المصاحف` |
| `Portal - Delete Mushaf Layouts` | `البوابة - حذف تخطيطات المصاحف` |
| `Mushaf layout with id {id} not found.` | `تخطيط المصحف بالمعرّف {id} غير موجود.` |
| `This layout is used by one or more assets and cannot be deleted.` | `هذا التخطيط مستخدم في مادة أو أكثر ولا يمكن حذفه.` |

Run `extendedmakemessages`, fill them in, verify 0 untranslated.

- [ ] **Step 8: Commit**

```bash
git add apps/core/permissions.py apps/core/ninja_utils/tags.py \
        apps/content/repositories/mushaf_layout.py \
        apps/content/services/mushaf_layout.py \
        apps/content/tests/services/test_mushaf_layout_service.py \
        locale/ar/LC_MESSAGES/django.po
git commit -m "feat: add mushaf layout permissions, repository and service"
```

---

### Task 9: `MushafLayout` portal CRUD endpoints

**Files:**
- Create: `apps/content/api/portal/mushaf_layouts.py`
- Test: `apps/content/tests/portal/mushaf_layouts/test_mushaf_layouts_api.py`

**Interfaces:**
- Consumes: `MushafLayoutService` (Task 8), `NinjaTag.MUSHAF_LAYOUTS`, the four permissions.
- Produces: `GET/POST /portal/mushaf-layouts/`, `GET/PATCH/DELETE /portal/mushaf-layouts/{layout_id}/`, returning `MushafLayoutOut {id, name, name_ar, name_en, page_count, assets_count, created_at, updated_at}`.

Routers under `apps/content/api/portal/` are auto-discovered by `config/portal_api.py` (`auto_discover_ninja_routers(portal_api, "api/portal")`). No registration step is needed.

Reads query the model directly in the view — this repo's portal-read rule. Writes go through the service.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/portal/mushaf_layouts/test_mushaf_layouts_api.py` (add an `__init__.py` to the new package directory):

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase


class MushafLayoutsApiTests(BaseTestCase):
    def test_list_where_layouts_exist_should_return_them(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT])
        baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.get("/portal/mushaf-layouts/")

        # Assert
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["items"]]
        self.assertIn("Madani 604", names)

    def test_create_where_valid_should_return_201_and_persist(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT])

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"name_en": "Indo-Pak 611", "name_ar": "الهندي ٦١١", "page_count": 611},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        self.assertTrue(MushafLayout.objects.filter(page_count=611).exists())

    def test_retrieve_where_layout_missing_should_return_404_with_error_name(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT])

        # Act
        response = self.client.get("/portal/mushaf-layouts/999999/")

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_delete_where_layout_in_use_should_return_400_with_error_name(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT])
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )

        # Act
        response = self.client.delete(f"/portal/mushaf-layouts/{layout.pk}/")

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_in_use")

    def test_create_where_user_lacks_permission_should_return_403(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT])

        # Act
        response = self.client.post(
            "/portal/mushaf-layouts/",
            data={"name_en": "Nope", "page_count": 1},
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/portal/mushaf_layouts/ -v`
Expected: FAIL — 404 on every route, the module does not exist.

- [ ] **Step 3: Write the endpoints**

Create `apps/content/api/portal/mushaf_layouts.py`, following the structure of `apps/content/api/portal/reciters.py`:

```python
import logging
from typing import Literal

from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from ninja import Field, Schema
from ninja.pagination import paginate
from pydantic import AwareDatetime

from apps.content.models import MushafLayout
from apps.content.services.mushaf_layout import MushafLayoutService
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.ordering_base import ordering
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.searching_base import searching
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice

router = ItqanRouter(tags=[NinjaTag.MUSHAF_LAYOUTS])
logger = logging.getLogger(__name__)


class MushafLayoutOut(Schema):
    id: int
    name: str
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int
    assets_count: int = Field(0, description="Number of assets using this layout")
    created_at: AwareDatetime
    updated_at: AwareDatetime


class MushafLayoutCreateIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int = Field(..., ge=1)


class MushafLayoutPatchIn(Schema):
    name_ar: str | None = None
    name_en: str | None = None
    page_count: int | None = Field(default=None, ge=1)


@router.get("mushaf-layouts/", response=list[MushafLayoutOut])
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)])
@searching(["name_ar", "name_en"])
@ordering(["name", "page_count", "created_at"])
@paginate
def list_mushaf_layouts(request: Request):
    return MushafLayout.objects.annotate(assets_count=Count("assets"))


@router.get(
    "mushaf-layouts/{layout_id}/",
    response={
        200: MushafLayoutOut,
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_MUSHAF_LAYOUT)])
def retrieve_mushaf_layout(request: Request, layout_id: int):
    try:
        return MushafLayout.objects.annotate(assets_count=Count("assets")).get(pk=layout_id)
    except MushafLayout.DoesNotExist as exc:
        raise ItqanError(
            error_name="mushaf_layout_not_found",
            message=_("Mushaf layout with id {id} not found.").format(id=layout_id),
            status_code=404,
        ) from exc


@router.post("mushaf-layouts/", response={201: MushafLayoutOut})
@permission_required([permission_class(PermissionChoice.PORTAL_CREATE_MUSHAF_LAYOUT)])
def create_mushaf_layout(request: Request, data: MushafLayoutCreateIn):
    layout = MushafLayoutService().create(
        name_ar=data.name_ar, name_en=data.name_en, page_count=data.page_count
    )
    return 201, layout


@router.patch(
    "mushaf-layouts/{layout_id}/",
    response={
        200: MushafLayoutOut,
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_UPDATE_MUSHAF_LAYOUT)])
def update_mushaf_layout(request: Request, layout_id: int, data: MushafLayoutPatchIn):
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    return MushafLayoutService().update(layout_id, **fields)


@router.delete(
    "mushaf-layouts/{layout_id}/",
    response={
        204: None,
        400: NinjaErrorResponse[Literal["mushaf_layout_in_use"]],
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
    },
)
@permission_required([permission_class(PermissionChoice.PORTAL_DELETE_MUSHAF_LAYOUT)])
def delete_mushaf_layout(request: Request, layout_id: int):
    MushafLayoutService().delete(layout_id)
    return 204, None
```

`assets_count` comes from the annotation in the read views. The create and update views return a model instance without it, so give `MushafLayoutOut.assets_count` a default of `0` (it already has one) or annotate on re-fetch — the default is fine, since the client re-lists after a write.

Match the `@searching` / `@ordering` decorator signatures to how `reciters.py` uses them; check that file if the arguments differ.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest apps/content/tests/portal/mushaf_layouts/ -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/content/api/portal/mushaf_layouts.py apps/content/tests/portal/mushaf_layouts/
git commit -m "feat: add mushaf layout portal CRUD endpoints"
```

---
### Task 10: Template on asset creation, output and filters

**Files:**
- Modify: `apps/content/api/portal/translations.py`
- Modify: `apps/content/api/portal/tafsirs.py`
- Modify: `apps/content/services/translation.py`
- Modify: `apps/content/services/tafsir.py`
- Modify: `apps/content/api/portal/filters.py`
- Test: `apps/content/tests/portal/test_asset_template_create.py`

**Interfaces:**
- Consumes: `AssetTemplateChoice` (Task 1), `MushafLayoutService.get_or_404` (Task 8), `Asset.save()` guard (Task 4).
- Produces: `template` and `mushaf_layout_id` on `TranslationCreateIn` / `TafsirCreateIn`; `template` and a nested `mushaf_layout` on the list and detail outputs; a `template` filter.

This closes immutability layers 1 and 2.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/portal/test_asset_template_create.py`:

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, LicenseChoice, MushafLayout
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher


class TranslationTemplateCreateTests(BaseTestCase):
    def _payload(self, **overrides):
        publisher = baker.make(Publisher)
        payload = {
            "name_en": "Test Translation",
            "description_en": "d",
            "license": LicenseChoice.CC0.value,
            "language": "en",
            "publisher_id": publisher.id,
            "template": AssetTemplateChoice.AYAH.value,
        }
        payload.update(overrides)
        return payload

    def test_create_where_template_is_page_and_no_layout_should_return_400(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_CREATE_TRANSLATION])

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_required")

    def test_create_where_template_is_ayah_and_layout_given_should_return_400(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_CREATE_TRANSLATION])
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(mushaf_layout_id=layout.id),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_allowed")

    def test_create_where_layout_does_not_exist_should_return_404(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_CREATE_TRANSLATION])

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=999999),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_name"], "mushaf_layout_not_found")

    def test_create_where_valid_page_template_should_persist_template_and_layout(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_CREATE_TRANSLATION])
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)

        # Act
        response = self.client.post(
            "/portal/translations/",
            data=self._payload(
                template=AssetTemplateChoice.PAGE.value, mushaf_layout_id=layout.id
            ),
            content_type="application/json",
        )

        # Assert
        self.assertEqual(response.status_code, 201)
        asset = Asset.objects.get(pk=response.json()["id"])
        self.assertEqual(asset.template, AssetTemplateChoice.PAGE)
        self.assertEqual(asset.mushaf_layout_id, layout.id)

    def test_update_where_template_sent_should_be_ignored_by_the_schema(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_UPDATE_TRANSLATION])
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.AYAH,
            license=LicenseChoice.CC0,
        )

        # Act
        response = self.client.put(
            f"/portal/translations/{asset.slug}/",
            data={"name_en": "Renamed", "template": AssetTemplateChoice.WORD.value},
            content_type="application/json",
        )

        # Assert
        asset.refresh_from_db()
        self.assertEqual(asset.template, AssetTemplateChoice.AYAH)

    def test_detail_where_asset_has_template_should_expose_it(self):
        # Arrange
        self.authenticate_user(permissions=[PermissionChoice.PORTAL_READ_TRANSLATION])
        asset = baker.make(
            Asset,
            category="translation",
            template=AssetTemplateChoice.WORD,
            license=LicenseChoice.CC0,
        )

        # Act
        response = self.client.get(f"/portal/translations/{asset.slug}/")

        # Assert
        self.assertEqual(response.json()["template"], "word")
        self.assertIsNone(response.json()["mushaf_layout"])
```

The create payload above lists only the fields this test needs. Check `TranslationCreateIn` for any other required field and add it — the test must exercise a real, accepted payload.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/portal/test_asset_template_create.py -v`
Expected: FAIL — `template` is rejected as an unknown field.

- [ ] **Step 3: Add the input fields**

In `apps/content/api/portal/translations.py`, on `TranslationCreateIn`:

```python
    template: AssetTemplateChoice
    mushaf_layout_id: int | None = None
```

Leave `TranslationPutIn` and any patch schema untouched. That absence is immutability layer 1 and must not be "fixed" later.

Import `AssetTemplateChoice` from `apps.content.models`.

Apply the identical change to `apps/content/api/portal/tafsirs.py`.

- [ ] **Step 4: Add the output fields**

In the same file:

```python
class MushafLayoutBriefOut(Schema):
    id: int
    name: str
    page_count: int
```

Add to both `TranslationListOut` and `TranslationDetailOut`:

```python
    template: AssetTemplateChoice | None = None
    mushaf_layout: MushafLayoutBriefOut | None = None
```

Mirror in `tafsirs.py`.

- [ ] **Step 5: Validate in the service**

In `apps/content/services/translation.py`, in the create path, before the asset is written:

```python
    def _resolve_layout(self, template: str, mushaf_layout_id: int | None) -> MushafLayout | None:
        """Validate the template/layout pairing and resolve the layout."""
        if template == AssetTemplateChoice.PAGE:
            if mushaf_layout_id is None:
                raise ItqanError(
                    error_name="mushaf_layout_required",
                    message=_("A page-based asset requires a mushaf layout."),
                    status_code=400,
                )
            return MushafLayoutService().get_or_404(mushaf_layout_id)
        if mushaf_layout_id is not None:
            raise ItqanError(
                error_name="mushaf_layout_not_allowed",
                message=_("Only page-based assets can have a mushaf layout."),
                status_code=400,
            )
        return None
```

Call it from create and pass `template=` and `mushaf_layout=` through to the repository.

Add the immutability guard (layer 2) to the update path:

```python
        if "template" in fields or "mushaf_layout_id" in fields:
            raise ItqanError(
                error_name="asset_template_immutable",
                message=_("An asset's template cannot be changed after creation."),
                status_code=400,
            )
```

Mirror both in `apps/content/services/tafsir.py`.

- [ ] **Step 6: Document the new errors on the endpoints**

On the translation and tafsir create views:

```python
        400: NinjaErrorResponse[Literal["mushaf_layout_required"]]
        | NinjaErrorResponse[Literal["mushaf_layout_not_allowed"]],
        404: NinjaErrorResponse[Literal["mushaf_layout_not_found"]],
```

merging with whatever those views already declare rather than replacing it.

On the update views, add `NinjaErrorResponse[Literal["asset_template_immutable"]]` to the 400 union.

- [ ] **Step 7: Add the filter**

In `apps/content/api/portal/filters.py`, add `template: AssetTemplateChoice | None = None` to the translation and tafsir filter schemas, following the existing field style in that file.

- [ ] **Step 8: Run the tests**

```bash
.venv/bin/pytest apps/content/tests/portal/test_asset_template_create.py -v
.venv/bin/pytest apps/content -q
```
Expected: both pass. Existing translation/tafsir create tests will fail for a missing `template` — add `"template": "ayah"` to their payloads.

- [ ] **Step 9: Localization**

Three new `_()` strings:

| msgid | msgstr |
| --- | --- |
| `A page-based asset requires a mushaf layout.` | `المادة المبنية على الصفحات تتطلب تخطيط مصحف.` |
| `Only page-based assets can have a mushaf layout.` | `تخطيط المصحف متاح فقط للمواد المبنية على الصفحات.` |

`An asset's template cannot be changed after creation.` was already translated in Task 4 — reuse it, do not duplicate the entry.

Run `extendedmakemessages`, verify 0 untranslated.

- [ ] **Step 10: Commit**

```bash
git add apps/content/ locale/ar/LC_MESSAGES/django.po
git commit -m "feat: accept and expose asset template on create"
```

---

## Phase 6 (backend half) — Importer, export, and the verse-sample guard

Numbered 6 in the spec, executed here so the backend PR is complete before the frontend starts.

### Task 11: Template-aware importer

**Files:**
- Modify: `apps/content/services/asset_content_import.py`
- Modify: `apps/content/repositories/asset_content.py`
- Test: `apps/content/tests/services/test_asset_content_import_templates.py`

**Interfaces:**
- Consumes: `UnitSpec` (Task 5).
- Produces: `parse_content_file(raw: bytes, spec: UnitSpec) -> list[ParsedEntry]` — signature gains the spec; `ParsedEntry` becomes `@dataclass(frozen=True) class ParsedEntry: unit_id: int; text: str`.

Column rules, per the spec:

| template | recognised columns |
| --- | --- |
| surah | `sura` + text |
| ayah | `sura` + `aya` + text (unchanged) |
| word | `word_id`, **or** `sura` + `aya` + `word`, plus text |
| page | `page` + text |

For the word template a `word_id` column takes precedence when present; the `sura`/`aya`/`word` triple is used only in its absence. A file carrying neither is rejected as `content_file_unparseable`.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/services/test_asset_content_import_templates.py`:

```python
from model_bakery import baker

from apps.content.models import Asset, AssetTemplateChoice, CategoryChoice, MushafLayout
from apps.content.services.asset_content_import import AssetContentParseError, parse_content_file
from apps.content.services.asset_templates import unit_spec_for
from apps.core.tests.base import BaseTestCase


class TemplateImportTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def _spec(self, template, layout=None):
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=template, mushaf_layout=layout
        )
        return unit_spec_for(asset), asset

    def test_parse_where_surah_file_should_key_by_sura_number(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.SURAH)
        raw = b"sura,text\n1,opening\n2,cow\n"  # suras 1 and 2 baked by bake_quran

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual([(p.unit_id, p.text) for p in parsed], [(1, "opening"), (2, "cow")])

    def test_parse_where_page_file_should_key_by_page_number(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        spec, asset = self._spec(AssetTemplateChoice.PAGE, layout=layout)
        raw = b"page,text\n1,first\n604,last\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual([(p.unit_id, p.text) for p in parsed], [(1, "first"), (604, "last")])

    def test_parse_where_word_file_has_word_id_should_prefer_it(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.WORD)
        # word id 2 is baked; the sura/aya/word triple is deliberately bogus so
        # only word_id precedence can satisfy the assertion
        raw = b"word_id,sura,aya,word,text\n2,99,99,99,gloss\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual(parsed[0].unit_id, 2)

    def test_parse_where_ayah_file_should_keep_working(self):
        # Arrange
        spec, asset = self._spec(AssetTemplateChoice.AYAH)
        raw = b"id,sura,aya,translation\n1,1,1,bismillah\n"

        # Act
        parsed = parse_content_file(raw, spec, asset)

        # Assert
        self.assertEqual(parsed[0].unit_id, 1)
        self.assertEqual(parsed[0].text, "bismillah")

    def test_parse_where_columns_do_not_match_template_should_raise(self):
        # Arrange
        layout = baker.make(MushafLayout, name="Madani 604", page_count=604)
        spec, asset = self._spec(AssetTemplateChoice.PAGE, layout=layout)
        raw = b"sura,aya,text\n1,1,x\n"

        # Act / Assert
        with self.assertRaises(AssetContentParseError):
            parse_content_file(raw, spec, asset)
```

Every page-template asset needs a layout — `asset_mushaf_layout_consistency`
rejects one without.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_content_import_templates.py -v`
Expected: FAIL — `parse_content_file()` takes 1 positional argument.

- [ ] **Step 3: Extend the header aliases**

In `apps/content/services/asset_content_import.py`, beside the existing alias sets:

```python
_PAGE_HEADERS = {"page", "page_no", "رقم الصفحة"}
_WORD_ID_HEADERS = {"word_id", "word_index"}
_WORD_POSITION_HEADERS = {"word", "position", "رقم الكلمة"}
```

Keep `_SURA_HEADERS`, `_AYA_HEADERS` and `_TEXT_HEADERS` exactly as they are — the ayah path must not change behaviour.

- [ ] **Step 4: Rework `ParsedEntry` and the parse signature**

```python
@dataclass(frozen=True)
class ParsedEntry:
    """One parsed row, resolved to the canonical id of its template's unit."""

    unit_id: int
    text: str


def parse_content_file(raw: bytes, spec: UnitSpec, asset: Asset) -> list[ParsedEntry]:
    """Parse an uploaded content file into rows keyed to the asset's template unit.

    Raises ``AssetContentParseError`` when the file's columns do not match the
    template — a surah file uploaded to a page-based asset is a user error, not
    something to guess at.
    """
```

Resolution per template:
- **surah** — `unit_id` is the `sura` column value, validated to be 1..114.
- **ayah** — resolve `(sura, aya)` through the existing `_ayah_id_by_sura_aya` map on `AssetContentRepository`.
- **word** — `word_id` when the column is present; otherwise resolve `(sura, aya, word)` through a new `_word_id_by_sura_aya_position` map.
- **page** — `unit_id` is the `page` column value, validated to be 1..`asset.mushaf_layout.page_count`.

- [ ] **Step 5: Add the word lookup map to the repository**

In `apps/content/repositories/asset_content.py`, beside `_ayah_id_by_sura_aya`:

```python
    def _word_id_by_sura_aya_position(self) -> dict[tuple[int, int, int], int]:
        """Canonical word ids keyed by (sura, ayah-in-sura, position-in-ayah)."""
        return {
            (sura_id, number_in_sura, position): word_id
            for word_id, sura_id, number_in_sura, position in Word.objects.values_list(
                "id", "sura_id", "ayah__number_in_sura", "position_in_ayah"
            )
        }
```

Import `Word` from `apps.quran.models`. This builds a 77,431-entry dict; it is used once per import, never per request.

- [ ] **Step 6: Update the call sites**

`import_uploaded_file_into_entries` in `apps/content/services/asset_content.py` calls `parse_content_file(raw)`. Change it to resolve the spec first:

```python
    spec = unit_spec_for(version.asset)
    parsed = parse_content_file(raw, spec, version.asset)
```

and pass the spec on to `replace_entries_from_parsed(version, spec, parsed)`, which writes `spec.field` instead of `ayah_id`.

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/pytest apps/content/tests/services/test_asset_content_import_templates.py -v
.venv/bin/pytest apps/content -q
```
Expected: both pass.

- [ ] **Step 8: Commit**

```bash
git add apps/content/ && git commit -m "feat: make the content importer template-aware"
```

---

### Task 12: Template-aware CSV export and the verse-sample guard

**Files:**
- Modify: `apps/content/repositories/asset_content.py`
- Modify: `apps/content/services/asset_verse_text.py`
- Test: `apps/content/tests/services/test_asset_content_export_templates.py`

**Interfaces:**
- Consumes: `UnitSpec` (Task 5).
- Produces: `entries_to_csv_bytes(version, spec, *, verbose=False)` and `snapshot_to_csv_bytes(snapshot, spec, *, verbose=False)` emitting the template's columns; `extract_verse_text` returning `None` for non-ayah assets.

- [ ] **Step 1: Write the failing test**

Create `apps/content/tests/services/test_asset_content_export_templates.py`:

```python
from model_bakery import baker

from apps.content.models import (
    Asset,
    AssetTemplateChoice,
    AssetVersion,
    AssetVersionEntry,
    CategoryChoice,
)
from apps.content.repositories.asset_content import AssetContentRepository
from apps.content.services.asset_templates import unit_spec_for
from apps.content.services.asset_verse_text import extract_verse_text
from apps.core.tests.base import BaseTestCase


class ExportTemplateTests(QuranDataMixin, BaseTestCase):
    def setUp(self):
        super().setUp()
        self.bake_quran()

    def test_entries_to_csv_where_surah_template_should_emit_a_sura_column(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.SURAH
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, sura_id=1, text="opening", order=1)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert
        header = csv_bytes.decode("utf-8-sig").splitlines()[0]
        self.assertIn("sura", header)
        self.assertNotIn("aya", header)

    def test_entries_to_csv_where_page_template_should_emit_a_page_column(self):
        # Arrange
        layout = baker.make("content.MushafLayout", name="Madani 604", page_count=604)
        asset = baker.make(
            Asset,
            category=CategoryChoice.TRANSLATION,
            template=AssetTemplateChoice.PAGE,
            mushaf_layout=layout,
        )
        version = baker.make(AssetVersion, asset=asset)
        AssetVersionEntry.objects.create(version=version, page_no=3, text="third", order=3)
        repo = AssetContentRepository()

        # Act
        csv_bytes = repo.entries_to_csv_bytes(version, unit_spec_for(asset))

        # Assert
        self.assertIn("page", csv_bytes.decode("utf-8-sig").splitlines()[0])

    def test_extract_verse_text_where_asset_is_word_based_should_return_none(self):
        # Arrange
        asset = baker.make(
            Asset, category=CategoryChoice.TRANSLATION, template=AssetTemplateChoice.WORD
        )

        # Act
        result = extract_verse_text(asset, surah=1, ayah=1)

        # Assert
        self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest apps/content/tests/services/test_asset_content_export_templates.py -v`
Expected: FAIL — `entries_to_csv_bytes()` takes 1 positional argument.

- [ ] **Step 3: Make the export template-aware**

In `apps/content/repositories/asset_content.py`, change the two CSV writers to take the spec and emit per-template headers:

| template | columns |
| --- | --- |
| surah | `sura,text` |
| ayah | `id,sura,aya,text` (unchanged from today) |
| word | `word_id,sura,aya,word,text` |
| page | `page,text` |

Keep the `verbose` flag's existing meaning for the ayah template so current exports are byte-identical.

- [ ] **Step 4: Guard the verse sampler**

In `apps/content/services/asset_verse_text.py`, at the top of `extract_verse_text`:

```python
    # Verse sampling reads a "surah:ayah"-keyed JSON payload, which only an
    # ayah-template asset produces. Other templates have no per-verse text.
    if asset.template != AssetTemplateChoice.AYAH:
        return None
```

Import `AssetTemplateChoice` from `apps.content.models`.

Find the sample-asset picker that feeds this (grep for `get_sample_asset` and `extract_verse_text` call sites) and add `template=AssetTemplateChoice.AYAH` to its queryset filter, so a non-ayah asset is never chosen as the sample in the first place.

- [ ] **Step 5: Run the tests**

```bash
.venv/bin/pytest apps/content/tests/services/test_asset_content_export_templates.py -v
.venv/bin/pytest apps/content apps/quran -q
```
Expected: both pass.

- [ ] **Step 6: Update the backend docs**

In `docs/ARCHITECTURE.md`:
- **Core Domain Models** — add `MushafLayout` and its relationship to `Asset`.
- **The ER mermaid diagram** — add the `MushafLayout` node, the `Asset.template` field, and the four unit columns on `AssetVersionEntry`.
- **Section 4 (Asset)** — note that translations and tafsirs carry an immutable `template`.
- **Multi-language content, availability & review** — the per-ayah delta wording now reads "per-unit"; fix it.

Fix any neighbouring statement you notice that this change made wrong, not only the lines you add.

Do **not** touch `docs-website/docs/` — the public developer API contract is unchanged.

- [ ] **Step 7: Final backend verification**

```bash
.venv/bin/pytest -q
msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null
.venv/bin/python manage.py compilemessages
```
Expected: full suite passes; msgfmt reports 0 untranslated and no errors; compilemessages succeeds.

Record the msgfmt line ("N translated, 0 untranslated") — it goes in the PR description.

- [ ] **Step 8: Commit**

```bash
git add apps/content/ docs/ARCHITECTURE.md
git commit -m "feat: template-aware export and ayah-only verse sampling"
```

---
## Phases 4 & 5 — Frontend (`cms-frontend`)

All remaining tasks run in the **`cms-frontend`** repo. Cut `feat/asset-templates` from `staging` there before starting, and never rename it after pushing.

The backend must be merged (or running locally) first: Task 6 renamed `ayah_id` / `surah_name` / `uthmani` to `unit_id` / `label` / `reference_text`, which is a breaking change the frontend lands with.

### Task 13: Template types, models and services

**Files:**
- Modify: `src/app/features/admin/models/asset-content.models.ts`
- Modify: `src/app/features/admin/services/asset-content.service.ts`
- Create: `src/app/features/admin/services/mushaf-layouts.service.ts`
- Test: `src/app/features/admin/services/mushaf-layouts.service.spec.ts`

**Interfaces:**
- Consumes: the backend endpoints from Tasks 6, 9 and 10.
- Produces:
  - `export type AssetTemplate = 'surah' | 'ayah' | 'word' | 'page';`
  - `ContentEntry` reshaped to `{ unit_type, unit_id, label, reference_text, sura, aya, text, source_text?, order }`
  - `ContentChange` reshaped to `{ unit_type, unit_id, label, change_type, old_text, new_text }`
  - `ContentEntryPatch` → `{ unit_id, text }`
  - `MushafLayout` → `{ id, name, page_count, assets_count }`
  - `MushafLayoutsService.list(): Observable<MushafLayout[]>`
  - `AssetContentService.listEntries(..., sura?: number)`

- [ ] **Step 1: Reshape the models**

In `src/app/features/admin/models/asset-content.models.ts`:

```ts
/** Content granularity of a text asset. Fixed when the asset is created. */
export type AssetTemplate = 'surah' | 'ayah' | 'word' | 'page';

export interface MushafLayout {
  id: number;
  name: string;
  page_count: number;
  assets_count: number;
}

export interface ContentEntry {
  unit_type: AssetTemplate;
  /** Canonical id of the unit: sura id, ayah id, word id, or page number. */
  unit_id: number;
  /** Identifying reference, e.g. "1. Al-Fatiha", "2:255", "2:255:4", "Page 42". */
  label: string;
  /** The Quranic text being annotated; empty for the page template. */
  reference_text: string;
  sura: number | null;
  aya: number | null;
  text: string;
  /** Source-language text for the same unit (translations only; read-only). */
  source_text?: string | null;
  order: number;
}

export interface ContentChange {
  unit_type: AssetTemplate;
  unit_id: number;
  label: string;
  change_type: 'added' | 'modified' | 'removed';
  old_text: string;
  new_text: string;
}

export interface ContentEntryPatch {
  unit_id: number;
  text: string;
}
```

`ContentEntriesResponse` keeps its `{ results, count }` shape — the backend envelope is unchanged.

- [ ] **Step 2: Add the `sura` filter to `listEntries`**

In `asset-content.service.ts`, extend the existing `listEntries` signature with an optional `sura` and append it only when set:

```ts
    let params = new HttpParams()
      .set('page', page.toString())
      .set('page_size', pageSize.toString());
    if (sura != null) {
      params = params.set('sura', sura.toString());
    }
```

`HttpParams` is immutable, so reassign rather than calling `.set` for its side effect.

Update the service's class doc comment: it is no longer "per-ayah", it is per-unit.

- [ ] **Step 3: Write the failing test for the layouts service**

Create `src/app/features/admin/services/mushaf-layouts.service.spec.ts`:

```ts
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';

import { MushafLayoutsService } from './mushaf-layouts.service';

describe('MushafLayoutsService', () => {
  let service: MushafLayoutsService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), MushafLayoutsService],
    });
    service = TestBed.inject(MushafLayoutsService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('unwraps the paginated envelope into a plain array', () => {
    // Arrange
    let received: unknown = null;

    // Act
    service.list().subscribe((layouts) => (received = layouts));
    const req = httpMock.expectOne((r) => r.url.endsWith('mushaf-layouts/'));
    req.flush({ results: [{ id: 1, name: 'Madani 604', page_count: 604, assets_count: 0 }], count: 1 });

    // Assert
    expect(received).toEqual([
      { id: 1, name: 'Madani 604', page_count: 604, assets_count: 0 },
    ]);
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `npx ng test --include='**/mushaf-layouts.service.spec.ts' --watch=false`
Expected: FAIL — cannot resolve `./mushaf-layouts.service`.

If the project runs tests differently, check `package.json` `scripts` and use the project's own test command.

- [ ] **Step 5: Write the service**

Create `src/app/features/admin/services/mushaf-layouts.service.ts`:

```ts
import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';

import { environment } from '../../../../environments/environment';
import type { MushafLayout } from '../models/asset-content.models';

/** Mushaf layouts — the pagination a page-based asset follows. */
@Injectable({ providedIn: 'root' })
export class MushafLayoutsService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.ADMIN_API_BASE_URL;

  /**
   * Every layout, for the create-asset selector. The list is small (one row per
   * mushaf printing), so it is fetched in a single page rather than paged.
   */
  list(): Observable<MushafLayout[]> {
    const params = new HttpParams().set('page_size', '1000');
    return this.http
      .get<{ results: MushafLayout[]; count: number }>(`${this.base}mushaf-layouts/`, { params })
      .pipe(map((response) => response.results));
  }
}
```

Confirm `environment.ADMIN_API_BASE_URL` is the name `asset-content.service.ts` uses and that it already ends with a slash; match it exactly.

- [ ] **Step 6: Run test to verify it passes**

Run: `npx ng test --include='**/mushaf-layouts.service.spec.ts' --watch=false`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/app/features/admin/models/asset-content.models.ts \
        src/app/features/admin/services/asset-content.service.ts \
        src/app/features/admin/services/mushaf-layouts.service.ts \
        src/app/features/admin/services/mushaf-layouts.service.spec.ts
git commit -m "feat: add template-shaped content models and mushaf layouts service"
```

---

### Task 14: The template badge

**Files:**
- Create: `src/app/shared/components/asset-template-badge/asset-template-badge.component.ts`
- Create: `src/app/shared/components/asset-template-badge/asset-template-badge.component.less`
- Create: `src/app/shared/components/asset-template-badge/asset-template-badge.component.spec.ts`
- Modify: `public/i18n/en.json`, `public/i18n/ar.json`

**Interfaces:**
- Consumes: `AssetTemplate`, `MushafLayout` (Task 13).
- Produces: `<app-asset-template-badge [template]="t" [layoutName]="name" />` — a standalone component.

- [ ] **Step 1: Add the translation keys**

In `public/i18n/en.json`, under the existing `ADMIN` tree (match the file's nesting — inspect it first):

```json
"ASSET_TEMPLATE": {
  "SURAH": "Surah based",
  "AYAH": "Ayah based",
  "WORD": "Word based",
  "PAGE": "Page based",
  "PAGE_WITH_LAYOUT": "Page based ({{layout}})",
  "LABEL": "Content template",
  "IMMUTABLE_HINT": "The template is fixed when the asset is created and cannot be changed.",
  "LAYOUT_LABEL": "Mushaf layout",
  "LAYOUT_PLACEHOLDER": "Select a mushaf layout"
}
```

In `public/i18n/ar.json`, the same keys:

```json
"ASSET_TEMPLATE": {
  "SURAH": "حسب السورة",
  "AYAH": "حسب الآية",
  "WORD": "حسب الكلمة",
  "PAGE": "حسب الصفحة",
  "PAGE_WITH_LAYOUT": "حسب الصفحة ({{layout}})",
  "LABEL": "قالب المحتوى",
  "IMMUTABLE_HINT": "يُحدَّد القالب عند إنشاء المادة ولا يمكن تغييره بعد ذلك.",
  "LAYOUT_LABEL": "تخطيط المصحف",
  "LAYOUT_PLACEHOLDER": "اختر تخطيط المصحف"
}
```

Both files must carry the identical key set. A key present in one and missing from the other renders the raw key path to users of that locale.

- [ ] **Step 2: Write the failing test**

Create `asset-template-badge.component.spec.ts`:

```ts
import { TestBed } from '@angular/core/testing';
import { TranslateModule } from '@ngx-translate/core';

import { AssetTemplateBadgeComponent } from './asset-template-badge.component';

describe('AssetTemplateBadgeComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AssetTemplateBadgeComponent, TranslateModule.forRoot()],
    }).compileComponents();
  });

  it('uses the plain key when the template is not page based', () => {
    // Arrange
    const fixture = TestBed.createComponent(AssetTemplateBadgeComponent);
    fixture.componentRef.setInput('template', 'word');

    // Act
    fixture.detectChanges();

    // Assert
    expect(fixture.componentInstance.translationKey()).toBe('ADMIN.ASSET_TEMPLATE.WORD');
  });

  it('uses the layout-qualified key when a page layout is given', () => {
    // Arrange
    const fixture = TestBed.createComponent(AssetTemplateBadgeComponent);
    fixture.componentRef.setInput('template', 'page');
    fixture.componentRef.setInput('layoutName', 'Madani 604');

    // Act
    fixture.detectChanges();

    // Assert
    expect(fixture.componentInstance.translationKey()).toBe('ADMIN.ASSET_TEMPLATE.PAGE_WITH_LAYOUT');
    expect(fixture.componentInstance.translationParams()).toEqual({ layout: 'Madani 604' });
  });

  it('renders nothing when the asset has no template', () => {
    // Arrange
    const fixture = TestBed.createComponent(AssetTemplateBadgeComponent);
    fixture.componentRef.setInput('template', null);

    // Act
    fixture.detectChanges();

    // Assert
    expect(fixture.nativeElement.textContent.trim()).toBe('');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx ng test --include='**/asset-template-badge.component.spec.ts' --watch=false`
Expected: FAIL — module not found.

- [ ] **Step 4: Write the component**

Create `asset-template-badge.component.ts`:

```ts
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { TranslateModule } from '@ngx-translate/core';

import type { AssetTemplate } from '../../../features/admin/models/asset-content.models';

/**
 * The "Ayah based" / "Word based" indicator shown on an asset.
 *
 * Renders nothing for an asset with no template — every category other than
 * translation and tafsir has none, and a blank badge reads as a bug.
 */
@Component({
  selector: 'app-asset-template-badge',
  standalone: true,
  imports: [TranslateModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (template()) {
      <span class="asset-template-badge" [class]="'asset-template-badge--' + template()">
        {{ translationKey() | translate: translationParams() }}
      </span>
    }
  `,
  styleUrl: './asset-template-badge.component.less',
})
export class AssetTemplateBadgeComponent {
  readonly template = input<AssetTemplate | null>(null);
  readonly layoutName = input<string | null>(null);

  readonly translationKey = computed(() => {
    const template = this.template();
    if (!template) {
      return '';
    }
    if (template === 'page' && this.layoutName()) {
      return 'ADMIN.ASSET_TEMPLATE.PAGE_WITH_LAYOUT';
    }
    return `ADMIN.ASSET_TEMPLATE.${template.toUpperCase()}`;
  });

  readonly translationParams = computed(() =>
    this.layoutName() ? { layout: this.layoutName() } : {}
  );
}
```

Create `asset-template-badge.component.less` with a small pill style, using the project's existing design tokens. Inspect a neighbouring shared component's `.less` file for the variable names in use rather than inventing colours.

- [ ] **Step 5: Run test to verify it passes**

Run: `npx ng test --include='**/asset-template-badge.component.spec.ts' --watch=false`
Expected: 3 passing.

- [ ] **Step 6: Place the badge**

Add `<app-asset-template-badge [template]="asset.template" [layoutName]="asset.mushaf_layout?.name ?? null" />` in three places, importing the standalone component into each:

1. `src/app/features/gallery/components/asset-card/` — the public asset card.
2. `src/app/features/admin/translations/components/translations-list/` and the tafsirs equivalent — the admin list row.
3. `src/app/features/admin/translations/components/translation-detail/` and the tafsirs equivalent — the detail header.

Add `template` and `mushaf_layout` to whichever TypeScript interfaces back those views.

- [ ] **Step 7: Verify the build**

Run: `npx ng build`
Expected: succeeds with no type errors.

- [ ] **Step 8: Commit**

```bash
git add src/app/shared/components/asset-template-badge/ src/app/features/ public/i18n/
git commit -m "feat: add asset template badge"
```

---
### Task 15: Template and layout selectors on the create forms

**Files:**
- Modify: `src/app/features/admin/translations/components/translation-form/translation-form.component.ts`
- Modify: `src/app/features/admin/translations/components/translation-form/translation-form.component.html`
- Modify: `src/app/features/admin/tafsirs/components/tafsir-form/tafsir-form.component.ts`
- Modify: `src/app/features/admin/tafsirs/components/tafsir-form/tafsir-form.component.html`
- Test: `src/app/features/admin/translations/components/translation-form/translation-form.component.spec.ts`

**Interfaces:**
- Consumes: `AssetTemplate`, `MushafLayoutsService` (Task 13); the i18n keys (Task 14).
- Produces: a `template` form control (required on create) and a `mushaf_layout_id` control (required iff `template === 'page'`), both disabled in edit mode.

- [ ] **Step 1: Write the failing test**

Create or extend `translation-form.component.spec.ts`:

```ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TranslateModule } from '@ngx-translate/core';

import { TranslationFormComponent } from './translation-form.component';

describe('TranslationFormComponent template controls', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TranslationFormComponent, TranslateModule.forRoot()],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('requires a template when creating', () => {
    // Arrange
    const fixture = TestBed.createComponent(TranslationFormComponent);
    fixture.detectChanges();
    const form = fixture.componentInstance.form;

    // Act
    form.get('template')!.setValue(null);

    // Assert
    expect(form.get('template')!.valid).toBe(false);
  });

  it('requires a layout only when the template is page based', () => {
    // Arrange
    const fixture = TestBed.createComponent(TranslationFormComponent);
    fixture.detectChanges();
    const form = fixture.componentInstance.form;

    // Act
    form.get('template')!.setValue('ayah');
    const layoutOptionalWhenAyah = form.get('mushaf_layout_id')!.valid;
    form.get('template')!.setValue('page');
    form.get('mushaf_layout_id')!.setValue(null);

    // Assert
    expect(layoutOptionalWhenAyah).toBe(true);
    expect(form.get('mushaf_layout_id')!.valid).toBe(false);
  });

  it('disables both controls in edit mode', () => {
    // Arrange
    const fixture = TestBed.createComponent(TranslationFormComponent);
    fixture.componentRef.setInput('slug', 'existing-translation');

    // Act
    fixture.detectChanges();

    // Assert
    expect(fixture.componentInstance.form.get('template')!.disabled).toBe(true);
    expect(fixture.componentInstance.form.get('mushaf_layout_id')!.disabled).toBe(true);
  });
});
```

Inspect `translation-form.component.ts` first: match the real name of the form property, the real edit-mode input (it may be a `slug` input, a route param, or an `asset` object), and the component's existing provider needs. The test must drive the component as it actually is.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx ng test --include='**/translation-form.component.spec.ts' --watch=false`
Expected: FAIL — no `template` control.

- [ ] **Step 3: Add the controls**

In the component's form construction:

```ts
      template: [null as AssetTemplate | null, Validators.required],
      mushaf_layout_id: [null as number | null],
```

Make the layout requirement conditional by reacting to the template control:

```ts
    this.form.get('template')!.valueChanges.subscribe((template) => {
      const layout = this.form.get('mushaf_layout_id')!;
      layout.setValidators(template === 'page' ? [Validators.required] : []);
      if (template !== 'page') {
        layout.setValue(null);
      }
      layout.updateValueAndValidity();
    });
```

Clearing the layout when the template moves off `page` matters: the backend rejects a non-page asset carrying a layout with `mushaf_layout_not_allowed`.

Disable both in edit mode, wherever the component decides it is editing:

```ts
    if (this.isEditMode()) {
      this.form.get('template')!.disable();
      this.form.get('mushaf_layout_id')!.disable();
    }
```

Load the layouts for the selector:

```ts
  private readonly layoutsService = inject(MushafLayoutsService);
  readonly layouts = signal<MushafLayout[]>([]);

  // in ngOnInit
  this.layoutsService.list().subscribe((layouts) => this.layouts.set(layouts));
```

- [ ] **Step 4: Add the markup**

In the form's `.html`, following the file's existing `nz-form-item` pattern:

```html
<nz-form-item>
  <nz-form-label [nzRequired]="!isEditMode()">
    {{ 'ADMIN.ASSET_TEMPLATE.LABEL' | translate }}
  </nz-form-label>
  <nz-form-control>
    <nz-select
      formControlName="template"
      [nzPlaceHolder]="'ADMIN.ASSET_TEMPLATE.LABEL' | translate"
    >
      <nz-option nzValue="surah" [nzLabel]="'ADMIN.ASSET_TEMPLATE.SURAH' | translate"></nz-option>
      <nz-option nzValue="ayah" [nzLabel]="'ADMIN.ASSET_TEMPLATE.AYAH' | translate"></nz-option>
      <nz-option nzValue="word" [nzLabel]="'ADMIN.ASSET_TEMPLATE.WORD' | translate"></nz-option>
      <nz-option nzValue="page" [nzLabel]="'ADMIN.ASSET_TEMPLATE.PAGE' | translate"></nz-option>
    </nz-select>
    @if (isEditMode()) {
      <span class="form-hint">{{ 'ADMIN.ASSET_TEMPLATE.IMMUTABLE_HINT' | translate }}</span>
    }
  </nz-form-control>
</nz-form-item>

@if (form.get('template')?.value === 'page') {
  <nz-form-item>
    <nz-form-label nzRequired>
      {{ 'ADMIN.ASSET_TEMPLATE.LAYOUT_LABEL' | translate }}
    </nz-form-label>
    <nz-form-control>
      <nz-select
        formControlName="mushaf_layout_id"
        [nzPlaceHolder]="'ADMIN.ASSET_TEMPLATE.LAYOUT_PLACEHOLDER' | translate"
      >
        @for (layout of layouts(); track layout.id) {
          <nz-option
            [nzValue]="layout.id"
            [nzLabel]="layout.name + ' (' + layout.page_count + ')'"
          ></nz-option>
        }
      </nz-select>
    </nz-form-control>
  </nz-form-item>
}
```

- [ ] **Step 5: Send the fields on create only**

Where the component builds its create payload, include `template` and `mushaf_layout_id`. Where it builds its **update** payload, include neither — the backend's `PutIn` schema does not accept them, and sending them would fail the request.

- [ ] **Step 6: Run test to verify it passes**

Run: `npx ng test --include='**/translation-form.component.spec.ts' --watch=false`
Expected: 3 passing.

- [ ] **Step 7: Mirror into the tafsir form**

Apply Steps 3–5 to `tafsir-form.component.ts` / `.html`. The markup and logic are identical; repeat them rather than extracting a shared component — two usages do not justify an abstraction, and the forms already diverge elsewhere.

- [ ] **Step 8: Verify the build**

Run: `npx ng build`
Expected: succeeds.

- [ ] **Step 9: Commit**

```bash
git add src/app/features/admin/
git commit -m "feat: add template and layout selectors to asset create forms"
```

---

### Task 16: Template-driven grid columns

**Files:**
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.ts`
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.html`
- Test: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.spec.ts`

**Interfaces:**
- Consumes: `ContentEntry`, `AssetTemplate` (Task 13).
- Produces: `buildColumnDefs()` returning template-appropriate columns; the grid reading `unit_id` where it read `ayah_id`.

This task keeps the existing **client-side** row model for every template. Task 17 adds the infinite model for `word` only.

- [ ] **Step 1: Write the failing test**

Create `asset-content-grid.component.spec.ts`:

```ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TranslateModule } from '@ngx-translate/core';

import { AssetContentGridComponent } from './asset-content-grid.component';

describe('AssetContentGridComponent column definitions', () => {
  function componentFor(template: string) {
    const fixture = TestBed.createComponent(AssetContentGridComponent);
    fixture.componentRef.setInput('template', template);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AssetContentGridComponent, TranslateModule.forRoot()],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
  });

  it('shows only the label and text columns for the page template', () => {
    // Arrange / Act
    const fields = componentFor('page')
      .buildColumnDefs()
      .map((col: { field?: string }) => col.field)
      .filter(Boolean);

    // Assert
    expect(fields).toEqual(['label', 'text']);
  });

  it('shows the reference text column for the ayah template', () => {
    // Arrange / Act
    const fields = componentFor('ayah')
      .buildColumnDefs()
      .map((col: { field?: string }) => col.field)
      .filter(Boolean);

    // Assert
    expect(fields).toContain('reference_text');
  });

  it('keeps the surah floating filter off the page template', () => {
    // Arrange / Act
    const columns = componentFor('page').buildColumnDefs();

    // Assert
    expect(columns.some((col: { floatingFilterComponent?: unknown }) => col.floatingFilterComponent)).toBe(
      false
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx ng test --include='**/asset-content-grid.component.spec.ts' --watch=false`
Expected: FAIL — the component has no `template` input.

- [ ] **Step 3: Add the template input and rebuild the columns**

Add to the component:

```ts
  readonly template = input<AssetTemplate | null>(null);
  readonly layoutName = input<string | null>(null);
```

Rewrite `buildColumnDefs()` to dispatch on it:

```ts
  buildColumnDefs(): ColDef[] {
    const template = this.template();
    const reference: ColDef[] =
      template === 'page'
        ? []
        : [
            {
              field: 'reference_text',
              headerName: this.translate.instant('ADMIN.CONTENT_EDITOR.COLUMNS.REFERENCE'),
              editable: false,
              flex: 1,
            },
          ];

    return [
      {
        field: 'label',
        headerName: this.translate.instant('ADMIN.CONTENT_EDITOR.COLUMNS.UNIT'),
        editable: false,
        width: 140,
        pinned: this.rtl() ? 'right' : 'left',
        // The surah filter only means something where rows carry a surah.
        ...(template === 'ayah' || template === 'word'
          ? { floatingFilterComponent: SurahFloatingFilterComponent, filter: true }
          : {}),
      },
      ...reference,
      {
        field: 'text',
        headerName: this.translate.instant('ADMIN.CONTENT_EDITOR.COLUMNS.TEXT'),
        editable: true,
        flex: 2,
      },
    ];
  }
```

Keep whatever extra columns the current implementation has (`source_text` for translations, the selection checkbox) and gate each the same way. Read the existing method before rewriting it; do not drop behaviour you did not account for.

- [ ] **Step 4: Switch the row key from `ayah_id` to `unit_id`**

Every place the component reads `row.ayah_id` — `pendingRows.set(row.ayah_id, …)`, `getRowId`, the patch payload builder — becomes `row.unit_id`. Search the file for `ayah_id` and `ayah` and fix each occurrence; the surah option builder that reads `row.surah_name` now reads `row.sura` and resolves the name from the reference data it already loads.

- [ ] **Step 5: Add the column header keys**

Add to both `public/i18n/en.json` and `public/i18n/ar.json` under `ADMIN.CONTENT_EDITOR.COLUMNS`:

| key | en | ar |
| --- | --- | --- |
| `UNIT` | `Reference` | `الموضع` |
| `REFERENCE` | `Quran text` | `نص القرآن` |
| `TEXT` | `Content` | `المحتوى` |

If `ADMIN.CONTENT_EDITOR.COLUMNS` already exists with keys for the current columns, extend it rather than replacing it.

- [ ] **Step 6: Pass the template in from the parents**

The grid's host components (the translation and tafsir content-editor pages) must pass `[template]="asset.template"` and `[layoutName]="asset.mushaf_layout?.name ?? null"`. Find them by searching for `app-asset-content-grid`.

- [ ] **Step 7: Run the tests**

```bash
npx ng test --include='**/asset-content-grid.component.spec.ts' --watch=false
npx ng build
```
Expected: 3 passing; build succeeds.

- [ ] **Step 8: Commit**

```bash
git add src/app/features/admin/components/asset-content-grid/ public/i18n/ src/app/features/admin/
git commit -m "feat: drive content grid columns from the asset template"
```

---

### Task 16A: Template-aware review grid

**Files:**
- Modify: `src/app/features/admin/models/asset-review.models.ts`
- Modify: `src/app/features/admin/components/asset-review-grid/asset-review-grid.component.html`
- Modify: `src/app/features/admin/components/asset-review-grid/asset-review-grid.component.spec.ts`

**Interfaces:**
- Consumes: Task 7A's reshaped `ReviewChangeOut`; `AssetTemplate` (Task 13).
- Produces: `ReviewChange` carrying `unit_type` / `unit_id` / `label` instead of `sura` / `aya` / `surah_name`.

- [ ] **Step 1: Reshape the model**

In `src/app/features/admin/models/asset-review.models.ts`, replace the three location fields on `ReviewChange`:

```ts
export interface ReviewChange {
  id: number;
  unit_type: AssetTemplate;
  /** Canonical id of the unit: sura id, ayah id, word id, or page number. */
  unit_id: number;
  /** Display reference, e.g. "2. Al-Baqara", "2:255", "2:255:4", "Page 42". */
  label: string;
  change_type: 'added' | 'modified' | 'removed';
  old_text: string;
  new_text: string;
  /** The last-approved text for this unit (the review baseline); empty if never approved. */
  baseline_text: string;
  commit_ref: string;
  commit_id: number;
  review_state: ReviewState;
  comment: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
}
```

Import `AssetTemplate` from `./asset-content.models`. Note the `baseline_text` doc comment changes from "this ayah" to "this unit".

- [ ] **Step 2: Update the grid markup**

In `asset-review-grid.component.html`, any cell rendering `{{ row.sura }}:{{ row.aya }}` or `{{ row.surah_name }}` becomes `{{ row.label }}`. Search the file for `sura`, `aya` and `surah_name` and replace each occurrence; a single `label` column replaces what were separate location columns.

- [ ] **Step 3: Update the existing spec**

`asset-review-grid.component.spec.ts` builds `ReviewChange` fixtures with the old fields. Update every fixture to the new shape — `unit_type: 'ayah'`, `unit_id: 1`, `label: '1:1'` — so the file compiles against the new interface.

- [ ] **Step 4: Run the tests**

```bash
npx ng test --include='**/asset-review-grid.component.spec.ts' --watch=false
npx ng build
```
Expected: passing; the build surfaces any missed `sura` / `aya` / `surah_name` reference as a type error. Fix each at its source rather than widening the interface.

- [ ] **Step 5: Commit**

```bash
git add src/app/features/admin/models/asset-review.models.ts \
        src/app/features/admin/components/asset-review-grid/
git commit -m "feat: render review changes by template unit label"
```

---

### Task 17: Infinite row model for the word template

**Files:**
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.ts`
- Modify: `src/app/features/admin/components/asset-content-grid/asset-content-grid.component.html`
- Test: `src/app/features/admin/components/asset-content-grid/asset-content-grid.datasource.spec.ts`

**Interfaces:**
- Consumes: `AssetContentService.listEntries(..., sura?)` (Task 13); `buildColumnDefs` (Task 16).
- Produces: `buildWordDatasource(): IDatasource` — an AG Grid infinite datasource; `rowModelType()` returning `'infinite'` for the word template and `'clientSide'` otherwise.

Per the approved design, the word editor trades client-side undo/redo and client-side filtering for the ability to scroll 77,431 rows. The other three templates keep the existing behaviour untouched.

- [ ] **Step 1: Write the failing test**

Create `asset-content-grid.datasource.spec.ts`:

```ts
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TranslateModule } from '@ngx-translate/core';

import { AssetContentGridComponent } from './asset-content-grid.component';

describe('AssetContentGridComponent word datasource', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AssetContentGridComponent, TranslateModule.forRoot()],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('uses the infinite row model only for the word template', () => {
    // Arrange
    const fixture = TestBed.createComponent(AssetContentGridComponent);

    // Act
    fixture.componentRef.setInput('template', 'word');
    fixture.detectChanges();
    const wordModel = fixture.componentInstance.rowModelType();
    fixture.componentRef.setInput('template', 'ayah');
    fixture.detectChanges();
    const ayahModel = fixture.componentInstance.rowModelType();

    // Assert
    expect(wordModel).toBe('infinite');
    expect(ayahModel).toBe('clientSide');
  });

  it('translates a block request into a page request and reports the total', () => {
    // Arrange
    const fixture = TestBed.createComponent(AssetContentGridComponent);
    fixture.componentRef.setInput('template', 'word');
    fixture.componentRef.setInput('slug', 'a-translation');
    fixture.componentRef.setInput('versionId', 7);
    fixture.detectChanges();
    const datasource = fixture.componentInstance.buildWordDatasource();
    const successCallback = jasmine.createSpy('successCallback');

    // Act
    datasource.getRows({
      startRow: 100,
      endRow: 200,
      successCallback,
      failCallback: jasmine.createSpy('failCallback'),
      context: {},
sortModel: [],
      filterModel: {},
    } as never);
    const req = httpMock.expectOne((r) => r.url.includes('entries/'));
    req.flush({ results: [{ unit_id: 101, text: '' }], count: 77431 });

    // Assert
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('100');
    expect(successCallback).toHaveBeenCalledWith([{ unit_id: 101, text: '' }], 77431);
  });
});
```

Match the component's real input names (`slug`, `versionId`, `kind`) — read the component before writing the test.

- [ ] **Step 2: Run test to verify it fails**

Run: `npx ng test --include='**/asset-content-grid.datasource.spec.ts' --watch=false`
Expected: FAIL — `rowModelType` and `buildWordDatasource` do not exist.

- [ ] **Step 3: Add the row-model switch**

```ts
  /**
   * Word assets have 77,431 units — far too many to hold client-side — so they
   * scroll through server-fetched blocks. Every other template stays on the
   * client-side model, which is what keeps undo/redo and the surah floating
   * filter working for the editors that already rely on them.
   */
  readonly rowModelType = computed<'infinite' | 'clientSide'>(() =>
    this.template() === 'word' ? 'infinite' : 'clientSide'
  );
```

Bind it in the template: `[rowModelType]="rowModelType()"`, and bind `[datasource]` only when it is `'infinite'`:

```html
<ag-grid-angular
  [rowModelType]="rowModelType()"
  [datasource]="rowModelType() === 'infinite' ? wordDatasource() : undefined"
  [cacheBlockSize]="100"
  ...
/>
```

- [ ] **Step 4: Build the datasource**

```ts
  /** An AG Grid infinite datasource backed by the paginated entries endpoint. */
  buildWordDatasource(): IDatasource {
    return {
      getRows: (params: IGetRowsParams) => {
        const pageSize = params.endRow - params.startRow;
        const page = Math.floor(params.startRow / pageSize) + 1;
        this.contentService
          .listEntries(this.kind(), this.slug(), this.versionId(), page, pageSize, this.suraFilter())
          .subscribe({
            next: (response) => params.successCallback(response.results, response.count),
            error: () => params.failCallback(),
          });
      },
    };
  }

  readonly wordDatasource = computed<IDatasource>(() => this.buildWordDatasource());
```

Import `IDatasource` and `IGetRowsParams` from `ag-grid-community`.

`cacheBlockSize` must equal the `pageSize` the datasource computes, or the page arithmetic drifts. Pin both to 100.

- [ ] **Step 5: Move the surah filter server-side for word**

Add a `suraFilter` signal, and for the word template render a surah `nz-select` in the toolbar instead of the in-column floating filter (Task 16 already excluded the floating filter from non-ayah templates — extend that exclusion to `word`):

```ts
  readonly suraFilter = signal<number | null>(null);

  onSuraFilterChange(sura: number | null): void {
    this.suraFilter.set(sura);
    // A new filter invalidates every cached block.
    this.gridApi?.refreshInfiniteCache();
  }
```

Revisit Task 16's `buildColumnDefs`: the floating filter must now be attached for `'ayah'` only, not `'ayah' || 'word'`. Change that condition to `template === 'ayah'`.

- [ ] **Step 6: Disable undo/redo for the word template**

The undo/redo buttons operate on client-side row state and do nothing under the infinite model. Hide them rather than leaving dead controls:

```html
@if (rowModelType() === 'clientSide') {
  <!-- existing undo / redo buttons -->
}
```

- [ ] **Step 7: Run the tests**

```bash
npx ng test --include='**/asset-content-grid*.spec.ts' --watch=false
npx ng build
```
Expected: all passing; build succeeds.

- [ ] **Step 8: Update `PROJECT_MAP.md`**

In `cms-frontend/PROJECT_MAP.md`, update `[ARCHITECTURE]` and `[SYSTEM_FLOW]`: the content editor is per-unit rather than per-ayah, the grid switches row model on the word template, and asset creation now takes a template. Ensure `[ORPHANS & PENDING]` is empty when the work is done.

- [ ] **Step 9: Commit**

```bash
git add src/app/features/admin/components/asset-content-grid/ PROJECT_MAP.md
git commit -m "feat: add infinite row model for word based content editing"
```

---

## Final verification

- [ ] **Backend**

```bash
cd itqan-cms-backend
.venv/bin/pytest -q
msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null
.venv/bin/python manage.py compilemessages
git log --oneline staging..feat/asset-templates
```
Expected: suite green; 0 untranslated; compilemessages succeeds; commits from Tasks 1–12 present.

- [ ] **Frontend**

```bash
cd cms-frontend
npx ng test --watch=false
npx ng lint
npx ng build
```
Expected: all green.

- [ ] **Manual smoke test**

1. Create a surah-based translation. Open its editor. Confirm 114 rows, all empty.
2. Type into row 3, save, reopen. Confirm the text survived and only one entry row exists in the database.
3. Try to change the template from the edit form. Confirm the control is disabled.
4. Create a page-based translation without a layout. Confirm the form blocks it.
5. Create a mushaf layout, then a page-based translation using it. Confirm the editor shows exactly `page_count` rows.
6. Open an existing ayah-based translation. Confirm it behaves exactly as before, undo/redo included.
7. Create a word-based translation. Confirm the grid scrolls, fetches blocks, and the surah selector narrows it.

`runserver` caches the compiled translation catalog per process — restart it before testing Arabic strings.

- [ ] **Open the PRs**

Backend first, then frontend. Both target `staging`. Put the msgfmt line in the backend PR description.

The frontend PR depends on the backend being deployed: Task 6 renamed `ayah_id` / `surah_name` / `uthmani` in the entries payload. Note that dependency in the frontend PR body.
