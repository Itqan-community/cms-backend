# Itqan CMS — Product Roadmap (1448 Q1 & Q2)

This document tracks planned work beyond the current MVP. It captures **what** we want
to build and **why**, not implementation detail — see the linked GitHub issues for
per-task acceptance criteria.

**Period:** Hijri 1448, Q1–Q2 (Muharram – Jumada al-Thani 1448 ≈ late June – mid December 2026)

**Execution board:** [**Fanar** — org project #12](https://github.com/orgs/Itqan-community/projects/12)
Every objective below is broken into GitHub issues on that board, tagged by epic, sized,
and sequenced. Issues live in
[`cms-backend`](https://github.com/Itqan-community/cms-backend/issues) (backend, infra,
audio, docs) and [`cms-frontend`](https://github.com/Itqan-community/cms-frontend/issues)
(admin/portal UI).

**Status legend:** ✅ Shipped · 🚧 In Progress · 📋 Planned · 💡 Idea (not yet scoped)

---

## Where we are today

Itqan CMS lets **Publishers** upload Quranic content (tafsir, translation, recitation,
mushaf) and **Developers** consume it through a public API. Core pieces already in place:

| Area | Status | Notes |
| --- | --- | --- |
| Content model (`Resource` → `Asset`, versioned, licensed) | ✅ Shipped | Request/approval access flow live. See [ARCHITECTURE.md](./ARCHITECTURE.md) |
| Developer auth (OAuth2 client-credentials) | ✅ Shipped | Requires a confidential backend client. See [AUTHENTICATION.md](./AUTHENTICATION.md) |
| API keys (`X-API-Key` via ninja-keys) | ✅ Shipped | Becomes the app-identity mechanism in §1 |
| Canonical Quran reference data (`apps/quran`) | ✅ Shipped | Sura/Ayah/Word — 114 / 6,236 / 77,432 rows + internal read API |
| Per-request usage tracking → Mixpanel | ✅ Shipped | `@track_usage` decorator, publisher + entity context |
| Tafsir & translation text editing (MVP) | 🚧 In progress | Portal CRUD + versioning |
| Ayah-level recitation timing | 🚧 Data exists | `start_ms`/`end_ms` per ayah stored; not yet served |

The core tension this roadmap addresses: developers want frictionless integration (no
backend, no PII handover), while publishers want visibility into how their licensed
content is used downstream — its reach, impact, and protection from unfair usage.

---

## 0. Finish current MVP — tafsir & translation editing 🚧

Carry-over. Portal CRUD + versioning for text assets, editable in the CMS frontend admin.
Unblocks everything downstream.

**Issue:** [#408](https://github.com/Itqan-community/cms-backend/issues/408)

---

## 1. Self-identifying authentication 📋 — High priority

### Problem

OAuth2 client-credentials requires a confidential backend to protect a `client_secret` —
a hard blocker for mobile/web-only developers (embedding secrets in client bundles is
explicitly disallowed today; see the DO/DON'T table in
[AUTHENTICATION.md](./AUTHENTICATION.md#security-best-practices)). Publishers separately
need downstream usage visibility without Itqan holding end-user PII.

### Direction

- **Apps identify themselves with the existing API key** (`X-API-Key`). One key = one app,
  owned by a logged-in developer.
- Apps additionally send an opaque, developer-chosen **per-end-user identifier** — never
  email, name, or phone. Itqan never holds identity data; the developer owns the mapping.
- Unlocks per-app **and** per-user analytics: unique users served, usage distribution,
  fair-use enforcement.

### Decisions (locked)

- **API keys are the app identity. OAuth2 Applications are NOT used for this epic**, and
  there is **no new app-identity model and no new app-id header**. The existing
  `ninja_keys`-based `APIKey` (`apps/users/models.py`) already satisfies the requirement
  that a developer log in before receiving a token.
- **The API key is a public identifier, not a secret.** It is safe to ship in frontend and
  mobile bundles; leakage is not a security incident. Consequently **reveal-once is
  dropped — the key is re-viewable** in the dashboard. Revocation stays (that's how abuse
  is stopped); rotation is reframed as "get a new identifier," not "recover from a leak."
- **Self-identification layers alongside OAuth2**, which keeps working unchanged.
- **Spoofing is accepted for Phase 1.** Identifiers are open by design. A stricter scheme
  only if abuse materializes.
- **Retention: indefinite** — the per-user identifier is fully anonymised, no PII, no
  deletion obligation.

> ⚠️ Making the key re-viewable is a real change: `ninja_keys` stores only a **hash**, so
> the raw key is currently unrecoverable by design. Storing it re-displayably is a
> deliberate departure from hashed-at-rest, justified only because the key is explicitly
> non-secret. See [#407](https://github.com/Itqan-community/cms-backend/issues/407).

### Issues

| # | Task |
| --- | --- |
| [#423](https://github.com/Itqan-community/cms-backend/issues/423) | Reuse existing API keys as the app identity (no OAuth apps, no new model) |
| [#407](https://github.com/Itqan-community/cms-backend/issues/407) | Reframe API key as a non-secret public identifier (semantics + docs) |
| [#409](https://github.com/Itqan-community/cms-backend/issues/409) | Adjust API-key auth path for non-secret public keys (CORS, exposure) |
| [#410](https://github.com/Itqan-community/cms-backend/issues/410) | Add per-end-user identifier: validation + request wiring |
| [#411](https://github.com/Itqan-community/cms-backend/issues/411) | Wire app + per-user identifiers into usage tracking (Mixpanel) |
| [cms-frontend#209](https://github.com/Itqan-community/cms-frontend/issues/209) | Present API key as an embeddable public identifier |

---

## 2. Ayah-by-ayah recitation delivery 📋 — High priority

### Problem

Recitations are served as **one audio file per surah** (`RecitationSurahTrack`). A
developer who wants a single ayah must download the whole surah and discard the rest —
wasteful for the dominant use case (ayah players, memorization apps, search results).

### What already exists

`RecitationAyahTiming` stores `start_ms`/`end_ms`/`duration_ms` per ayah against each
surah track. The offsets are there; nothing serves per-ayah audio yet.

### Decisions

- **Full precompute** — slice all surah tracks into per-ayah files up front.
- **Fades at cut boundaries** to avoid clicks/artifacts.
- **Ayah ranges: yes** (e.g. 5–10), served as one combined file. De-scope to single-ayah
  if clean combining proves expensive.
- **`ffmpeg` is the suggested tool** — precise ms-resolution cuts (`-ss`/`-to`), fade
  filters (`afade`), stream-copy where possible. Prefer it directly over wrappers like
  pydub, which shell out to ffmpeg anyway while hiding the flags that matter for clean
  boundaries.

> ⚠️ **Storage sizing must be re-validated before committing to full precompute.** With
> Recitation folders (§3), the object count becomes `folders × 114 surahs × ayahs-per-surah`,
> not one variant. Slicing must also **invalidate the recitation response cache**, or stale
> audio gets served after a re-slice.

### Issues

| # | Task |
| --- | --- |
| [#412](https://github.com/Itqan-community/cms-backend/issues/412) | Build audio-slicing pipeline: precompute per-ayah files |
| [#413](https://github.com/Itqan-community/cms-backend/issues/413) | Persist per-ayah audio references (model + migration) |
| [#414](https://github.com/Itqan-community/cms-backend/issues/414) | Public API: serve single-ayah recitation audio |
| [#415](https://github.com/Itqan-community/cms-backend/issues/415) | Ayah-range recitation delivery (combined file) |
| [cms-frontend#205](https://github.com/Itqan-community/cms-frontend/issues/205) | Admin: preview/verify per-ayah slices |

---

## 3. Recitation folders 📋 — Medium-high priority

### Problem

The same recitation often exists in several variants — clear, with echo/delay, different
bitrates, video. Modelling each as a separate `Asset` fragments SEO and forces listeners
through extra clicks to find the version they want.

### Direction

Insert a **folder** layer in the hierarchy: `Asset → RecitationFolder → RecitationSurahTrack`.
Each folder is one variant of the same recitation and holds all 114 surahs.

### Decisions

- **Exactly one default folder per asset**, enforced by a partial unique constraint.
  Serving rule: **no filter → default folder; filter → that exact folder.**
- **Each folder carries its own ayah timings.** Echo and delay shift where each ayah
  starts, so variants cannot share a timing set. Since `RecitationAyahTiming` FKs to
  `track`, timings become per-folder automatically once tracks are re-parented — the real
  deliverable is **admin-supplied independent timings per folder**. Automatic re-timing
  (forced alignment) is an explicit follow-on, not in scope.
- **Cache keys must include the folder dimension** so default and echo don't collide.

### Issues

| # | Task |
| --- | --- |
| [#418](https://github.com/Itqan-community/cms-backend/issues/418) | Add `RecitationFolder` model between Asset and track (+ default flag) |
| [#419](https://github.com/Itqan-community/cms-backend/issues/419) | Migration + backfill: wrap existing tracks in a default folder |
| [#420](https://github.com/Itqan-community/cms-backend/issues/420) | Re-scope ayah timings per folder |
| [#421](https://github.com/Itqan-community/cms-backend/issues/421) | Serve folders in public + tenant APIs |
| [#424](https://github.com/Itqan-community/cms-backend/issues/424) | Folder-aware portal upload endpoints |
| [cms-frontend#208](https://github.com/Itqan-community/cms-frontend/issues/208) | Content-admin UI: folder switcher + set default |

---

## 4. Itqan Dependabot & asset package manager 📋 — Medium-high priority

### Problem

Text assets are downloaded once and bundled into apps, then never updated — while
publishers keep correcting and improving them. Readers get stale content; publishers'
fixes never reach the field.

### Direction

The dependency-management experience developers already know from `pip` / pub.dev / npm:

- **Manifest file** — a project declares its Itqan assets with pinned versions
  (à la `requirements.txt` / `pubspec.yaml`). `AssetVersion` already uses semver.
- **Registry API** — resolve a manifest to concrete `AssetVersion`s and fetch artifacts.
- **CLI installer** — `itqan install` / `itqan sync`, the `pip install -r` / `uv sync` /
  `npm install` equivalent: reads the manifest, resolves pins, and materializes assets
  into an `assets/` folder. Idempotent, lockfile-driven, CI-friendly.
- **Dependabot-style updater** — a new `AssetVersion` opens a PR bumping the pin in
  consuming repos.

### Notes

- Builds on the existing `PACKAGE` distribution channel
  ([ARCHITECTURE.md](./ARCHITECTURE.md#distribution-channels)).
- **The packaged artifact format is a prerequisite**, not an afterthought: assets are
  versioned DB entries plus files, not bundles. Registry and installer both need that
  shape defined first.
- Pipeline fetches should self-identify (§1) so publisher metrics cover package
  distribution too, not just live API calls.

### Issues

| # | Task |
| --- | --- |
| [#416](https://github.com/Itqan-community/cms-backend/issues/416) | Define asset manifest format + version-pinning spec |
| [#425](https://github.com/Itqan-community/cms-backend/issues/425) | Define packaged asset artifact format |
| [#417](https://github.com/Itqan-community/cms-backend/issues/417) | Package registry API: resolve & fetch pinned versions |
| [#422](https://github.com/Itqan-community/cms-backend/issues/422) | CLI installer: `itqan install` |
| [#426](https://github.com/Itqan-community/cms-backend/issues/426) | Updater — GitHub App auth, repo opt-in & manifest discovery |
| [#427](https://github.com/Itqan-community/cms-backend/issues/427) | Updater — open/refresh PRs on new `AssetVersion` |

---

## 5. Audit log 📋 — Medium-high priority

### Problem

There is no record of who changed what, and no way to reverse an action after the fact.

### Decisions (locked)

- **`django-simple-history`**, chosen for full row snapshots — a diff-only log can't
  reliably reconstruct state, and "reverse any action on demand" needs snapshots.
- **Audit history lives in a SEPARATE DATABASE**, routed via `DATABASE_ROUTERS`. This is
  what rules out DB triggers (they can't cross a database boundary) and mandates
  application-level writes. `history_user` is stored as a plain `history_user_id` since
  FKs can't cross databases.
- **Tracked:** all `content` app models (plus the forthcoming `RecitationFolder`), all
  `users` models, all `publishers` models.
  **Excluded:** `UsageEvent` (obsolete, being deleted) and the `quran` app (immutable
  reference data).

> ⚠️ **The main correctness risk** is that simple-history hooks signals, so
> `bulk_create` / `bulk_update` / `queryset.update()` **bypass it silently**. The codebase
> already uses these on the tafsir/translation write path — exactly where reversibility
> matters most. That gap is tracked as a bug, not an enhancement.

### Issues

| # | Task |
| --- | --- |
| [#429](https://github.com/Itqan-community/cms-backend/issues/429) | Provision separate audit database + `DATABASE_ROUTERS` |
| [#430](https://github.com/Itqan-community/cms-backend/issues/430) | Add `django-simple-history`: install, settings, middleware |
| [#431](https://github.com/Itqan-community/cms-backend/issues/431) | Enable history on tracked models |
| [#432](https://github.com/Itqan-community/cms-backend/issues/432) | Fix bulk operations to preserve history |
| [#433](https://github.com/Itqan-community/cms-backend/issues/433) | Reversal capability: revert to a prior state |
| [#434](https://github.com/Itqan-community/cms-backend/issues/434) | Audit-log reading surface + retention |

---

## 6. Developer-ready data views 📋 — Medium priority

### Problem

Developers need to see the shape of the data — schema, relationships, realistic samples —
before committing to build against it. A generated OpenAPI spec alone doesn't communicate
that.

### Direction

A developer-facing view per entity (Sura/Ayah/Word, Tafsir, Translation, Recitation
timing) showing structure in plain terms next to a real sample — a real ayah with its
tafsir, translation, and recitation timing attached. Mostly presentation; models and
internal read APIs already exist.

> ⚠️ **Blocked on an open decision:** public docs site vs. authenticated developer portal.
> That choice determines the frontend stack and the auth on the sample endpoints, so it
> must be settled before work starts.

### Issues

| # | Task |
| --- | --- |
| [#428](https://github.com/Itqan-community/cms-backend/issues/428) | Backend: sample-data API for developer-ready views |
| [cms-frontend#210](https://github.com/Itqan-community/cms-frontend/issues/210) | Frontend: developer-ready data views |

---

## 7. Usage insight dashboards 📋 — Medium / Low priority

Publisher-facing (impact + unfair-usage visibility) and developer-facing (own app
patterns) dashboards, once the per-user identifier flows through usage tracking.

> ⚠️ **Blocked on a decision owned by [#411](https://github.com/Itqan-community/cms-backend/issues/411):**
> whether the per-user identifier is persisted first-party (`UsageEvent`) or queried from
> Mixpanel. "Unique end-users served" can't be built until that's settled.

### Issues

| # | Task |
| --- | --- |
| [cms-frontend#206](https://github.com/Itqan-community/cms-frontend/issues/206) | Publisher usage-insight dashboard |
| [cms-frontend#207](https://github.com/Itqan-community/cms-frontend/issues/207) | Developer usage-insight dashboard |

---

## Sequencing rationale

1. **Finish the MVP** (§0) — unblocks everything downstream.
2. **Self-identifying auth** (§1) — highest leverage: unblocks integrations that otherwise
   won't happen, and gives publishers the transparency they're asking for.
3. **Recitation folders** (§3) — lands before ayah slicing, because slicing must be
   folder-aware and per-folder timings change the slicing math.
4. **Ayah-by-ayah recitation** (§2) — concrete and scoped; builds on timing data that
   already exists.
5. **Dependabot & package manager** (§4) — benefits from §1 landing first so pipeline
   fetches are attributable per app.
6. **Audit log** (§5) — independent of the above; sequenced by capacity, with the bulk-ops
   gap prioritized because it's a correctness issue on the MVP write path.
7. **Developer-ready data views** (§6) — compounds in value as the content types above
   come online, so the sample data reflects the full experience.
8. **Usage dashboards** (§7) — follows the §1 wiring.

---

**See also:**

- [Fanar execution board](https://github.com/orgs/Itqan-community/projects/12) — live status
- [ARCHITECTURE.md](./ARCHITECTURE.md) — current system architecture
- [AUTHENTICATION.md](./AUTHENTICATION.md) — current authentication; extended per [§1](#1-self-identifying-authentication--high-priority)
- [CONTRIBUTING.md](../CONTRIBUTING.md) — how to pick up an issue
