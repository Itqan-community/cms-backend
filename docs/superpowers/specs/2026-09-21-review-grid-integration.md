# Integration note: reconciling `feature/review-grid` with asset templates

**Status:** action required at merge time — **not** before.
**Owner:** whoever merges the *second* of these two branches into `staging`.

## The situation

Two branches are in flight and they disagree about one API shape.

| branch | frontend `ReviewChange` expects | backend `ReviewChangeOut` returns |
| --- | --- | --- |
| `staging` (today) | — | `sura`, `aya`, `surah_name` |
| `feature/review-grid` | `sura`, `aya`, `surah_name` | — (uses staging's backend) |
| `feat/asset-templates` | — (review grid not present) | `unit_type`, `unit_id`, `label` |

`feature/review-grid` is **correct against its own base**. Do not "fix" it while
`staging` still returns `sura`/`aya`/`surah_name` — that would break it against
the very branch it targets.

`feat/asset-templates` had to change the shape: text assets can now be keyed to a
sura, word or mushaf page rather than an ayah, so `AssetVersionChange.ayah` became
nullable. The old resolvers read `obj.ayah.sura_id`, which raises `AttributeError`
on any non-ayah change row — a 500 on the review page. Task 7A replaced them.

## The trigger

Whichever branch merges to `staging` **second**, apply the change below in the
same merge. Until then, do nothing.

If `feat/asset-templates` merges first, the review page on `feature/review-grid`
will render blank location cells and then break — the same way the content editor
broke when a stale frontend met the new backend.

## The change — three sites, frontend only

### 1. `src/app/features/admin/models/asset-review.models.ts`

```diff
+import type { AssetTemplate } from './asset-content.models';
+
 export interface ReviewChange {
   id: number;
-  sura: number;
-  aya: number;
-  surah_name: string;
+  unit_type: AssetTemplate;
+  /** Canonical id of the unit: sura id, ayah id, word id, or page number. */
+  unit_id: number;
+  /** Display reference, e.g. "2. Al-Baqara", "2:255", "2:255:4", "Page 42". */
+  label: string;
   change_type: 'added' | 'modified' | 'removed';
   old_text: string;
   new_text: string;
-  /** The last-approved text for this ayah (the review baseline); empty if never approved. */
+  /** The last-approved text for this unit (the review baseline); empty if never approved. */
   baseline_text: string;
   commit_ref: string;
   commit_id: number;
   review_state: ReviewState;
   comment: string;
   reviewed_by: string | null;
   reviewed_at: string | null;
 }
```

`AssetTemplate` is `'surah' | 'ayah' | 'word' | 'page'`, exported from
`src/app/features/admin/models/asset-content.models.ts`.

### 2. `src/app/features/admin/components/asset-review-grid/asset-review-grid.component.html` — line ~72

```diff
-                <td>{{ row.surah_name }} {{ row.sura }}:{{ row.aya }}</td>
+                <td>{{ row.label }}</td>
```

The backend composes `label` in exactly the four formats the content editor uses,
so the review page and the editor name a unit identically:

| template | label |
| --- | --- |
| surah | `1. Al-Fatiha` |
| ayah | `2:255` |
| word | `2:255:4` |
| page | `Page 42` |

### 3. `src/app/features/admin/components/asset-review-grid/asset-review-grid.component.spec.ts` — fixture at ~line 23

```diff
-    sura: 1,
-    aya: 1,
-    surah_name: 'الفاتحة',
+    unit_type: 'ayah',
+    unit_id: 1,
+    label: '1:1',
```

## Verification

`strictTemplates` is on, so `npx tsc --noEmit -p tsconfig.app.json` will surface
any missed read — including inside `.html` files. Note `npm run type-check` is a
**no-op** in this repo (root tsconfig has `files: []` plus project references), so
use the explicit project flags.

```
npx tsc --noEmit -p tsconfig.app.json
npx tsc --noEmit -p tsconfig.spec.json
npm test -- --watch=false
npm run lint
```

## Backend reference

Authoritative shape, `apps/content/api/portal/asset_review.py::ReviewChangeOut`:

```
id, unit_type, unit_id, label, change_type, old_text, new_text,
baseline_text, commit_ref, commit_id, review_state, comment,
reviewed_by, reviewed_at
```

Two related fixes landed alongside it in Task 7A, both silent-data bugs rather
than crashes, and both already covered by backend tests:

- `changes_for` deduplicated on `DISTINCT ON (ayah_id)`. Every non-ayah row has
  `ayah_id IS NULL`, so all of them collapsed into a single review row — edit ten
  suras, the reviewer saw one. Now keyed on a coalesced unit key via a ranked
  window.
- The `baseline_text` subquery correlated on `ayah_id = OuterRef("ayah_id")`,
  which is `NULL = NULL` → never true for non-ayah rows, so the baseline was
  always blank. Same coalesced key fixes it.

Neither is visible from the frontend diff above, but both are why the review page
behaves correctly for non-ayah assets once this lands.
