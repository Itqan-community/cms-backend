# Asset Templates for Text Assets — Design

**Date:** 2026-09-17
**Status:** Approved for planning
**Repos:** `itqan-cms-backend` (primary), `cms-frontend`

## Problem

Text assets (translations and tafsirs) are hardcoded to ayah granularity.
`AssetVersionEntry` carries a non-null FK to `quran.Ayah` with a unique
constraint on `(version, ayah)`; `AssetVersionChange`, the content importer,
the CSV export, the diff/review pipeline and the portal editor grid all inherit
that assumption.

Publishers need to produce text content keyed to other units of the Quran:
per surah, per word, and per mushaf page. A page-based asset depends on which
printed mushaf it follows, since page counts differ between printings.

## Requirements

1. Four templates: **surah**, **ayah**, **word**, **page**.
2. Every translation and tafsir belongs to exactly one template.
3. The template is chosen at creation and is **immutable** afterwards.
4. The asset carries a visible indicator of its template ("Ayah based",
   "Word based", …).
5. The template is a real storage and editing granularity, not a label:
   content rows are keyed to the template's unit.
6. The editor shows **every unit of the template**, whether or not content
   exists for it — a new surah-based asset opens on 114 empty rows.
7. Page counts are per-mushaf and entered by a user.

## Decisions

These were settled during brainstorming and are not open for re-litigation
during implementation.

| Decision | Resolution |
| --- | --- |
| Template meaning | Real storage/editing granularity |
| Scope | `translation` and `tafsir` only; all other categories keep `template = NULL` |
| Existing data | Backfilled to `ayah` |
| Page modelling | A named, reusable `MushafLayout` (name + page count) |
| Page → ayah map | **Rejected.** An ayah can straddle a page boundary, so a page→ayah-range map is lossy. Pages are opaque numbered slots. |
| Full-coverage rows | Enumerated virtually (left join), never materialised as empty DB rows |
| Word editor (77,431 units) | AG Grid infinite row model |
| Infinite grid scope | **Word only.** Surah/ayah/page keep the existing client-side grid so the working ayah editor does not regress. |

### Rejected alternatives

- **Generic `unit_type` + `unit_ref` column** on `AssetVersionEntry`. Rejected:
  drops the FK to `quran.Ayah` (losing DB integrity and the
  `select_related("ayah__sura")` the grid already relies on for surah name and
  Uthmani text) and forces a rewrite of every existing entry row.
- **One entry table per template.** Rejected: multiplies the entry *and*
  change/diff/review/import/publish machinery by four.
- **Materialising empty coverage rows** (as `ensure_mushaf_coverage` does).
  Rejected: a word-based asset would write 77,431 blank rows per version per
  language.

## Data model

### `AssetTemplateChoice`

In `apps/content/models.py`:

```python
class AssetTemplateChoice(models.TextChoices):
    SURAH = "surah", _("Surah based")
    AYAH  = "ayah",  _("Ayah based")
    WORD  = "word",  _("Word based")
    PAGE  = "page",  _("Page based")
```

### `MushafLayout` (new)

Lives in `apps/content/models.py`, beside `Reciter` / `Riwayah` / `Qiraah` —
the established home for admin-managed lookup data, and the app whose
`translation.py` already exists.

```python
class MushafLayout(BaseModel):
    name = models.CharField(max_length=128, unique=True)   # e.g. "Madani 604"
    page_count = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
```

Registered in `apps/content/translation.py` for `name_ar` / `name_en`.

### `Asset` additions

```python
template      = models.CharField(max_length=10, choices=AssetTemplateChoice, null=True, blank=True)
mushaf_layout = models.ForeignKey(MushafLayout, on_delete=models.PROTECT, null=True, blank=True, related_name="assets")
```

Two check constraints:

- `asset_template_required_for_text`:
  `category IN (translation, tafsir)` ⟺ `template IS NOT NULL`.
- `asset_mushaf_layout_consistency`:
  `template = 'page'` ⟺ `mushaf_layout IS NOT NULL`. This needs **three**
  branches, and every branch must be NULL-free. `template = 'page'` evaluates
  to SQL NULL when `template IS NULL`, and Postgres accepts a CHECK whose
  result is NULL — so any branch that can yield NULL for a
  (`template IS NULL`, `mushaf_layout` SET) row leaves the hole open and lets a
  font or recitation asset carry a mushaf layout. The `page` branch therefore
  needs an explicit `template__isnull=False` guard alongside its equality test,
  and a third branch pins `template IS NULL ⟹ mushaf_layout IS NULL`.

### `AssetVersionEntry` and `AssetVersionChange`

`ayah` becomes nullable and gains three siblings on **both** models:

```python
sura    = models.ForeignKey("quran.Sura", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
ayah    = models.ForeignKey("quran.Ayah", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
word    = models.ForeignKey("quran.Word", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
page_no = models.PositiveSmallIntegerField(null=True, blank=True)
```

One check constraint per model, `*_exactly_one_unit`: exactly one of the four
is non-null.

Uniqueness needs no new mechanism. Postgres treats NULLs as distinct in a
unique index, so the existing `unique_entry_per_version_ayah` keeps working
unchanged, and three sibling constraints — `unique_entry_per_version_sura`,
`unique_entry_per_version_word`, `unique_entry_per_version_page` — follow the
same plain `UniqueConstraint(fields=[...])` pattern. Same for the four
`unique_change_per_version_*` constraints.

`order` keeps its current role: the canonical index of the unit, for display
ordering.

**Not enforceable in the database:** that an entry's unit type matches its
asset's template. `template` lives two tables away (`Entry → Version → Asset`).
This is a service-layer invariant, asserted in `AssetContentService` on every
write path.

### Immutability

Three layers, cheapest first:

1. `template` and `mushaf_layout` are absent from `TranslationPutIn` and
   `TafsirPutIn`. Nothing can send them. This is the primary defence.
2. A guard in the asset update service raising
   `ItqanError(error_name="asset_template_immutable", status_code=400)`
   with a `gettext_lazy` message, covering any other write path.
3. A guard in `Asset.save()` comparing against the value captured in
   `from_db`, so a stray `obj.template = ...; obj.save()` from a shell,
   the admin, or a future service raises rather than silently mutating.
   No extra query — the original value rides along on the instance.

Django admin renders both fields readonly once `obj.pk` exists.

## Template descriptor

One new module, `apps/content/services/asset_templates.py`, holding the
four-way branch so it exists in exactly one place. Every consumer — the
entries endpoint, the patch path, the diff pipeline, the importer, the CSV
export — consults it rather than branching itself.

```python
@dataclass(frozen=True)
class UnitSpec:
    template: AssetTemplateChoice
    field: str                 # "sura" | "ayah" | "word" | "page_no"

    def total(self, asset: Asset) -> int: ...
    def units(self, asset: Asset) -> Sequence: ...   # canonical units, ordered
```

| template | `field` | canonical units | count |
| --- | --- | --- | --- |
| surah | `sura` | `Sura.objects.all()` | 114 |
| ayah | `ayah` | `Ayah.objects.select_related("sura")` | 6,236 |
| word | `word` | `Word.objects.select_related("ayah", "sura")` | 77,431 |
| page | `page_no` | generated `range(1, layout.page_count + 1)` | layout-defined |

The `page` spec returns a lightweight ordered sequence rather than a queryset,
since there is no page table. Ninja's paginator slices it correctly; the
entries view must not assume a `QuerySet`.

## API surface

### Blast radius

`AssetVersionEntry` appears nowhere outside `apps/content/api/portal/`. The
public, tenant and developers APIs serve text assets as files
(`AssetVersion.file_url`). This change is confined to the portal editor, the
importer, the CSV export, and the diff/review pipeline.

One exception: `apps/content/services/asset_verse_text.py::extract_verse_text`
feeds the public sample-data endpoint by reading the version JSON keyed
`"surah:ayah"`. That lookup is meaningless for a surah, word or page asset.
**Resolution:** the sample picker filters to `template = ayah` assets only;
non-ayah assets yield no verse sample.

### Create and update

`TranslationCreateIn` / `TafsirCreateIn` gain:

```python
template: AssetTemplateChoice
mushaf_layout_id: int | None = None
```

Validated in `TranslationService` / `TafsirService`:

| Condition | Error | Status |
| --- | --- | --- |
| `template = page` and no layout id | `mushaf_layout_required` | 400 |
| `template != page` and a layout id given | `mushaf_layout_not_allowed` | 400 |
| Layout id does not exist | `mushaf_layout_not_found` | 404 |

`TranslationPutIn` / `TafsirPutIn` gain neither field (immutability layer 1).

`TranslationListOut` / `TranslationDetailOut` and the tafsir equivalents gain
`template` and a nested `mushaf_layout: {id, name, page_count} | None`. The
portal filter schemas gain `template`.

### Entries endpoint

`GET content/{category}/{slug}/versions/{version_id}/entries/` changes from
"paginate stored entries" to "paginate the canonical unit set, left-joined
with stored entry text". The `@paginate` limit/offset contract is unchanged,
which is what the infinite-scroll grid needs.

A fresh surah-based asset returns 114 rows of empty text having written zero
DB rows.

`EntryOut` becomes template-shaped — one schema, not four:

```python
class EntryOut(Schema):
    unit_type: AssetTemplateChoice
    unit_id: int                  # sura id | ayah id | word id | page number
    label: str                    # "1. Al-Fatiha" | "2:255" | "2:255:4" | "Page 42"
    reference_text: str           # arabic sura name | uthmani ayah | the word | "" for page
    sura: int | None              # context; null for page
    aya: int | None               # context; null for surah and page
    text: str
    source_text: str | None = None
    order: int
```

`label` is the unit's identifying reference and is always non-empty;
`reference_text` is the Quranic text being annotated and is empty only for the
page template, which has no canonical text of its own. For the surah template
`label` carries the number and transliterated name while `reference_text`
carries the Arabic name, so the two never merely repeat each other.

This renames the current `ayah_id` / `surah_name` / `uthmani` fields. The
rename is deliberate — one shape for all templates, no legacy aliases. The
frontend grid migrates with it.

`EntryPatchRow.ayah_id` becomes `unit_id`. `ChangeOut` receives the same
treatment as `EntryOut`.

The entries endpoint accepts an optional `sura` query parameter, used by the
word grid's server-side surah filter (see Editor below).

### Review surface

`apps/content/api/portal/asset_review.py` builds `ReviewChangeOut` from
`obj.ayah.sura_id`, `obj.ayah.number_in_sura` and `obj.ayah.sura.name`. Once
`ayah` is nullable, a surah, word or page change row makes each of those raise
`AttributeError` — a 500 on the review page.

`ReviewChangeOut` therefore replaces `sura` / `aya` / `surah_name` with
`unit_type` / `unit_id` / `label`, resolving the label the same way `EntryOut`
does so the review page and the editor name a unit identically. The review
repository's `select_related` widens from `ayah__sura` to cover all four units,
keeping the changes list a single query.

The frontend `ReviewChange` model and `asset-review-grid` follow: one `label`
column replaces the separate location columns.

### MushafLayout portal CRUD

A small portal surface at `apps/content/api/portal/mushaf_layouts.py`,
modelled on the existing `reciters.py`: list, create, retrieve, update,
delete. Reads query the model directly in the view per this repo's portal-read
rule; writes go through a service and repository. Delete is blocked by the
`PROTECT` FK once any asset references the layout.

A page-based asset cannot be created before a layout exists.

## Importer and export

`apps/content/services/asset_content_import.py` becomes template-aware through
its existing header-alias mechanism:

| template | recognised columns |
| --- | --- |
| surah | sura, text |
| ayah | sura, aya, text (unchanged from today) |
| word | either a global `word_id` column, or `sura` + `aya` + `word` (position in ayah), plus text |
| page | page, text |

For the word template, a `word_id` column takes precedence when present; the
`sura` + `aya` + `word` triple is used only in its absence. A file carrying
neither is rejected as `content_file_unparseable`.

`ParsedEntry` resolves to `(unit_id, text)`. The repository's
`_ayah_id_by_sura_aya` map gains a word equivalent keyed
`(sura, aya, position_in_ayah)`.

`AssetContentRepository.entries_to_csv_bytes` and `snapshot_to_csv_bytes`
mirror the same columns per template.

The existing `content_file_unparseable` error covers a file whose columns do
not match the asset's template.

## Editor (cms-frontend)

### Template indicator

A shared `asset-template-badge` component rendering "Surah based" / "Ayah
based" / "Word based" / "Page based (Madani 604)". Placed on the asset card,
the admin list row, and the asset detail header. Translation keys added in
both `ar` and `en`.

### Creation forms

`translation-form` and `tafsir-form` gain a required template selector. A
layout selector appears only when `page` is chosen, populated from the
MushafLayout portal endpoint. On edit, both render readonly with a tooltip
explaining that the template is fixed at creation.

### Content grid

`asset-content-grid` builds its column definitions from the template:

| template | left columns |
| --- | --- |
| surah | surah number, surah name |
| ayah | reference (`2:255`), surah name, Uthmani text |
| word | reference (`2:255:4`), surah name, the word |
| page | page number |

Row model by template:

- **surah, ayah, page** — the existing client-side row model, unchanged.
  Undo/redo and the surah floating filter keep working exactly as today.
- **word** — AG Grid's infinite row model (Community edition), backed by the
  already-paginated entries endpoint. Consequences, accepted:
  - no client-side multi-step undo/redo in the word editor;
  - the surah filter becomes the endpoint's `sura` query parameter.

The component branches on template to pick the row model. This is two paths in
one component, chosen deliberately over one path, because unifying on the
infinite model would force a server-side rebuild of undo/redo and filtering
and regress the ayah editor currently in production.

## Migrations

Order matters — constraints must land after the backfill.

| # | Migration | Note |
| --- | --- | --- |
| 0062 | Create `MushafLayout` (+ `name_ar` / `name_en`) | register in `translation.py` first |
| 0063 | Add `Asset.template` (nullable), `Asset.mushaf_layout` | metadata-only in Postgres |
| 0064 | **Data:** backfill `template = 'ayah'` for every translation and tafsir | reversible (→ NULL) |
| 0065 | Add the two `Asset` check constraints | must follow 0064 |
| 0066 | `AssetVersionEntry` + `AssetVersionChange`: `ayah` → nullable, add `sura` / `word` / `page_no`, add `*_exactly_one_unit` to each model, plus the three sibling unique constraints on each (six in total) | no rows modified |

Dropping `NOT NULL` and adding nullable columns are metadata-only operations in
Postgres. Adding a `CheckConstraint` is not: it takes an `ACCESS EXCLUSIVE`
lock and validates the whole table. `assetversionentry` holds up to 6,236 rows
per version per language, so migration 0066 adds its check constraint as
`NOT VALID` via `SeparateDatabaseAndState`, and a separate migration 0067
runs `VALIDATE CONSTRAINT`.

The second migration is load-bearing, not tidiness: a Django migration is
atomic by default and Postgres holds the `ACCESS EXCLUSIVE` taken by
`ADD CONSTRAINT … NOT VALID` until commit, so validating in the same
migration scans the whole table under that lock — the very thing the split
avoids. Only a separate transaction releases it, letting `VALIDATE` run under
`SHARE UPDATE EXCLUSIVE`, which permits concurrent reads and writes.

Every existing entry row already has `ayah` set, so the exactly-one constraint
is satisfied by construction and validation cannot fail.

## Testing

Repo conventions apply throughout: `BaseTestCase` (never a raw
`django.test.TestCase`), explicit `# Arrange` / `# Act` / `# Assert` comments,
`test_<function>_where<criteria>_should<result>` naming, `pytest` as the
runner, `self.authenticate_user` inside the test body, `patch.object` against
the imported symbol at the call site, and `error_name` asserted on every 4xx
response — not just the status code.

**Backend**

- Model constraints: template required iff translation/tafsir; `page` ⟺ layout;
  entry and change exactly-one-unit; the six new unique constraints (three per model).
- Immutability at all three layers, including that `PutIn` cannot carry the
  field and that `Asset.save()` raises on a mutated template.
- `UnitSpec` totals per template (114 / 6,236 / 77,431 / `page_count`).
- Entries endpoint: a fresh surah asset returns 114 empty rows and writes zero
  DB rows; word pagination returns correct blocks at an offset; a page asset
  returns exactly `layout.page_count` rows; the `sura` filter narrows the word
  set.
- `patch_entries` writes the correct FK column per template and rejects a unit
  that does not match the asset's template.
- Publish and diff per template, including `AssetVersionChange` rows carrying
  the right unit.
- Importer across all four header shapes, plus `content_file_unparseable` when
  the columns do not match the template.
- CSV export columns per template.
- Create endpoint errors: `mushaf_layout_required`, `mushaf_layout_not_allowed`,
  `mushaf_layout_not_found`.
- MushafLayout CRUD, including delete blocked by `PROTECT`.
- A migration test for the 0064 backfill, following the existing
  `apps/content/tests/migrations/` precedent.
- `extract_verse_text` returns no sample for a non-ayah asset.

**Frontend**

- Template selector required on create; layout selector shown iff `page`;
  both readonly on edit.
- Badge renders the right label per template, in both languages.
- Grid column definitions per template.
- Word grid infinite datasource requests the right blocks and applies the
  `sura` filter server-side.

## Localization

A hard gate in this repo. Every new `_(...)` string gets an Arabic `msgstr`:

1. `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header`
2. Fill in every new `msgstr` in `locale/ar/LC_MESSAGES/django.po`.
3. `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null`
   must report **0 untranslated** and no errors.
4. No stray `fuzzy` flags on real entries.
5. `compilemessages` must succeed.

The frontend needs matching `ar` and `en` keys for the badge labels, the
template selector, the layout selector, and the immutability tooltip.

Note for manual testing: `runserver` caches the compiled catalog per process
and will not pick up a new `.mo` without a restart.

## Documentation

- `docs/ARCHITECTURE.md` — Core Domain Models, the ER mermaid diagram, the
  Asset section, and the multi-language content section. Add `MushafLayout`
  and `Asset.template`.
- `cms-frontend/PROJECT_MAP.md` — `[ARCHITECTURE]` and `[SYSTEM_FLOW]`.
- **Not** `docs-website/docs/` — the public developer API contract is
  unchanged, since entries never left the portal surface.

## Rollout

Two repos, two branches, two PRs. Backend lands first; the frontend depends on
its API.

Branches cut from `staging`, named `feat/asset-templates`. PRs target
`staging`. Per this repo's rules, commits are made by the user, never by the
agent. Do not rename a pushed frontend branch — doing so has previously closed
an open PR rather than retargeting it.

Phases:

1. Schema, backfill, constraints, immutability. Nothing user-visible.
2. Template descriptor and the virtually-enumerated entries endpoint; patch and
   diff per template.
3. Create endpoints, list/detail output, MushafLayout portal CRUD.
4. Frontend badge, template selector, layout selector.
5. Grid: template-driven columns for surah/ayah/page, then the word infinite
   datasource.
6. Importer and CSV export per template.

Phases 1–3 are backend-only and independently shippable. Phase 4 requires
phase 3. Phase 5 requires phase 2. Phase 6 requires phase 2 (it uses the
template descriptor) but is independent of phases 4 and 5.

## Open risks

- **Migration 0066 lock duration** on a large `assetversionentry` table. The
  `NOT VALID` + `VALIDATE` split is the mitigation; confirm the production row
  count before running it.
- **Frontend name proximity.** `cms-frontend` already has a
  `MushafsLayoutComponent` in `features/admin/mushafs/` — an unrelated Angular
  routing shell. New pieces live under a separate `mushaf-layouts` folder;
  imports will read similarly and need care.
- **Word-level volume.** 77,431 units per version per language. Entries stay
  sparse (only edited units are stored), which is what keeps this viable; any
  future change that materialises coverage rows would break that.
