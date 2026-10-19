# Usage Reports — Plan 3: Reports API (backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One query engine over the traffic rollups and events that serves four report scopes
(publisher portal, Itqan admin, developer account, public gallery counts) with summary,
timeseries and breakdown reports, CSV export, admin leaderboard and unseen-traffic
reconciliation, the metric definitions and the disclaimers the frontend must show.

**Architecture:** `services/usage_reports.py` owns the engine: parameter validation, the scope
(which assets/apps a caller may see), metric definitions, caching, the privacy floor and the
previous-period comparison. `repositories/usage_reports.py` owns every ORM query: totals and
series read `TrafficDaily`/`TrafficHourly`; only unique metrics read `TrafficEvent` (or
`TrafficMonthlyUniques` beyond event retention). Thin django-ninja views in
`api/portal/usage_reports.py` (publisher + admin) and `api/internal/usage_reports.py`
(developer + public) build a scope and call the engine. The 2026-10-13
`/portal/usage/downloads/*` endpoints are removed (no consumers).

**Tech Stack:** Django 5.2, django-ninja, Postgres 17, Django cache (Redis in production).

**Spec:** `docs/superpowers/specs/2026-10-18-usage-reports-design.md` §6 (privacy floor), §8,
§9, §10 (frontend needs), §13, §18, §19. Plans 1–2: `2026-10-18-usage-reports-1-collection.md`,
`2026-10-18-usage-reports-2-attribution.md`.

## Global Constraints

- All plan 1–2 constraints apply: `BaseTestCase`, AAA comments, test names
  `test_<fn>_where_<criteria>_should_<expected>`, `patch.object(target, symbol.__name__)`,
  `uv run --frozen` (revert `uv.lock` if it changes), pre-commit **one file at a time**,
  localized `_()` strings with 0 untranslated, docs updated, settings optional with defaults.
- Branch `feat/usage-reports-api` from `origin/feat/usage-reports-attribution` (PR #556); the PR
  targets that branch.
- 4xx tests assert `error_name`, not only the status code.
- Reports never scan `TrafficEvent` for additive metrics. Query counts are pinned by tests.
- Cache keys include the scope identity, the active language and every parameter.

## Rulings (spec gaps decided here; recorded in spec §20)

1. **Paths.** The root mount is the public developers API, so the admin scope lives on the
   portal API: `/portal/admin/usage/…` (Itqan staff = `is_staff`). Developer:
   `/cms-api/developers/usage/…`. Public: `/cms-api/assets/{id}/usage-counts/` (same asset
   lookup as the gallery detail endpoint). Publisher: `/portal/usage/…`.
2. **Engine in a service even for portal reads.** The portal "query in the view" rule is for
   pass-through reads; here four scopes share validation, caching, privacy and comparison logic.
3. **Summary always carries the previous period** (same length, immediately before).
   `compare=previous_period` adds a `previous` series to timeseries and `previous` values to
   breakdown rows. Leaderboard = breakdown by `publisher|asset` with comparison on.
4. **Unique metrics beyond retention** (range starting before the retention cutoff) come from
   `TrafficMonthlyUniques` as the **sum of monthly distinct counts** (`uniques_basis: "monthly"`),
   only when the filters are limited to the scope, `asset_id` and `app`; otherwise the value is
   `null` (`uniques_basis: "unavailable"`). Inside retention they are exact distincts
   (`"events"`).
5. **Privacy floor** (developer scope breakdowns): a row whose distinct listeners (non-bot,
   counted statuses, the metric's kinds) in retained events are fewer than 3 returns `"<3"`; the
   `other` row is omitted there. Public counts expose only all-time totals.
6. **Public counts**: `plays`, `downloads` (= downloads + CLI installs, the gallery line has one
   "downloads" figure), `apps` (identified apps with ≥ 1 play, download or API call), each
   floored to two significant figures; 404 `usage_counts_disabled` unless
   `PUBLIC_USAGE_COUNTS_ENABLED`; cached 1 h per asset and language.
7. **CSV export** (publisher and admin): one row per period × asset with the additive metrics
   (`plays, downloads, installs, api_calls, views, requests, bytes`); unique metrics are
   excluded (not additive across rows).
8. **`data_updated_at`** = newest error-free run of the Logpush import or the Django fold-in.
9. **Hour-of-week** buckets come from hourly rollups shifted to `tz`; zones with non-hour offsets
   are bucketed by the hour they fall in (backlog).
10. New settings: `PUBLIC_USAGE_COUNTS_ENABLED` (False), `USAGE_REPORTS_CACHE_SECONDS` (600).

## Interfaces

```python
# apps/usage_tracking/services/usage_reports.py
Metric = Literal["plays", "downloads", "installs", "api_calls", "requests", "bytes",
                 "unique_listeners", "unique_downloaders", "unique_end_users", "views"]
Granularity = Literal["hour", "day", "week", "month"]
DIMENSIONS: dict[str, str]   # api name -> column ("asset" -> "asset_id", "app" -> "app_id", ...)

@dataclass(frozen=True)
class ReportFilters:  # validated query parameters
    start_date: date; end_date: date
    asset_id: int | None; category: str | None; kind: str | None; channel: str | None
    platform: str | None; app: int | None; country: str | None; language: str | None
    version_id: int | None; surah: int | None

@dataclass(frozen=True)
class ReportScope:
    name: str                          # "publisher" | "admin" | "developer"
    cache_key: str                     # who is asking (publisher ids / "all" / user id)
    assets: QuerySet | None            # Asset rows the caller may see (None = everything)
    app_ids: tuple[int, ...] | None    # developer apps (None = any)
    publisher_ids: tuple[int, ...] | None  # for monthly uniques (None = all)
    privacy_floor: bool
    dimensions: frozenset[str]         # allowed split/breakdown dimensions

def publisher_scope(request) -> ReportScope
def admin_scope(request, publisher_id: int | None) -> ReportScope
def developer_scope(request) -> ReportScope
def summary(scope, filters) -> dict
def timeseries(scope, filters, metric, granularity, split_by, top, compare) -> dict
def breakdown(scope, filters, metric, by, limit, compare, tz) -> dict
def export_csv(scope, filters, granularity) -> HttpResponse
def reconciliation(filters, publisher_id, limit) -> dict
def public_counts(asset) -> dict
```

Errors (`ItqanError`, localized): `invalid_range`, `range_too_large`, `invalid_metric_for_kind`,
`asset_not_found`, `app_not_found`, `invalid_timezone`, `invalid_dimension`,
`usage_counts_disabled`, `permission_denied` (403).

## Review Focus

1. A publisher (or a member without `X-Tenant`) can never read another publisher's assets,
   through `asset_id`, `category`, `version_id`, splits, labels or the CSV.
2. A developer sees only rows of apps whose `UsageApp.user` is the caller, including when
   passing another user's `app`.
3. Unique metrics are never summed across days/rows from rollups; previous-period and "other"
   values for uniques are true distincts.
4. Query count per endpoint is constant as data grows (pinned with `assertNumQueries`).
5. The cache never serves one scope's (or language's) response to another.
6. Public counts 404 while the flag is off and never expose a hidden/tenant-restricted asset.

---

### Task 1: Parameters, validation and metric catalogue

**Files:** Create `apps/usage_tracking/services/usage_reports.py`; test
`apps/usage_tracking/tests/test_usage_reports_params.py`.

- [ ] **Step 1: Failing tests** — `validate_filters` rejects `end < start` (`invalid_range`),
  > 3660 days (`range_too_large`), hourly > 31 days (`range_too_large`); `check_metric_kind`
  rejects `plays` with `kind=version_file` (`invalid_metric_for_kind`) and accepts `requests`
  with any kind; `previous_period(2026-10-10..2026-10-16)` is `2026-10-03..2026-10-09`;
  `parse_tz("Mars/Base")` raises `invalid_timezone`.
- [ ] **Step 2: Run** `uv run --frozen pytest -q apps/usage_tracking/tests/test_usage_reports_params.py` — FAIL (ImportError).
- [ ] **Step 3: Implement** the metric catalogue (`ROLLUP_METRICS`: field + kinds;
  `UNIQUE_METRICS`: kinds, statuses, identity column, monthly measure), `DIMENSIONS`,
  `METRIC_DEFINITIONS` and `DISCLAIMERS` (lazy-translated), validation helpers.
- [ ] **Step 4: Run** — PASS. Commit `feat(usage): validate usage report parameters and define report metrics`.

### Task 2: Report repository and engine (summary, timeseries, breakdown)

**Files:** Create `apps/usage_tracking/repositories/usage_reports.py`; modify the service;
test `apps/usage_tracking/tests/test_usage_reports_engine.py`.

- [ ] **Step 1: Failing tests** (admin scope, data built with `TrafficDaily`/`TrafficHourly`
  rows and `TrafficEvent` rows):
  - summary: plays/downloads/installs/api_calls/views/requests/bytes for the range with
    previous-period values and `change`; integrating apps counts identified apps with sessions;
    unique listeners are distinct over the range (same listener on two days = 1);
  - summary with `asset_id`: `latest_version_share` = latest-version downloads+installs ÷ all;
  - timeseries day granularity zero-fills; week buckets start on Monday; month buckets on day 1;
    `split_by=country&top=1` returns the top key plus `other`; uniques per bucket are distinct;
    `compare=previous_period` adds an aligned `previous` series;
  - breakdown by asset carries labels; by `hour_of_week` with `tz=Asia/Riyadh` shifts by +3 h;
  - unique metrics beyond retention use monthly uniques (`uniques_basis="monthly"`), or `null`
    with an incompatible filter (`"unavailable"`).
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** the repository (scope/filter `Q` builders, rollup aggregates,
  bucketed series, grouped breakdowns, event distincts, monthly uniques, labels,
  `data_updated_at`) and the engine functions with caching (`USAGE_REPORTS_CACHE_SECONDS`).
- [ ] **Step 4: Run** — PASS. Commit `feat(usage): add the usage report query engine`.

### Task 3: Publisher endpoints, CSV export, removal of the download-stats endpoints

**Files:** Create `apps/usage_tracking/api/usage_schemas.py`, `apps/usage_tracking/api/portal/usage_reports.py`;
delete `apps/usage_tracking/api/portal/downloads.py`, `apps/usage_tracking/tests/test_portal_downloads.py`;
test `apps/usage_tracking/tests/test_portal_usage_reports.py`.

- [ ] **Step 1: Failing tests** — `/portal/usage/summary|timeseries|breakdown|export/`:
  403 `permission_denied` without `PORTAL_READ_USAGE`; own assets only (other publisher's
  `asset_id` → 404 `asset_not_found`; other publisher's rows absent from totals, splits and
  CSV); member of no publisher → zeros; CSV header and rows; constant query counts; second
  identical request served from cache (0 report queries).
- [ ] **Step 2–4:** run (FAIL), implement, run (PASS). Commit
  `feat(usage): serve publisher usage reports and CSV export` and, separately,
  `refactor(usage): remove the superseded download statistics endpoints`.

### Task 4: Itqan admin endpoints

**Files:** Modify `apps/usage_tracking/api/portal/usage_reports.py`; test
`apps/usage_tracking/tests/test_admin_usage_reports.py`.

- [ ] **Step 1: Failing tests** — `/portal/admin/usage/…`: non-staff → 403 `permission_denied`;
  all publishers by default (API calls without an asset included); `publisher_id` narrows;
  `leaderboard/?by=publisher` ranks with previous values; `reconciliation/` returns reads,
  edge requests and unseen (`max(reads − edge, 0)` per object-hour) in total, per asset and per
  day; CSV has a publisher column.
- [ ] **Step 2–4:** run, implement, run. Commit `feat(usage): serve Itqan admin usage reports, leaderboard and reconciliation`.

### Task 5: Developer endpoints and the privacy floor

**Files:** Create `apps/usage_tracking/api/internal/usage_reports.py`; test
`apps/usage_tracking/tests/test_developer_usage_reports.py`.

- [ ] **Step 1: Failing tests** — `/cms-api/developers/usage/…`: anonymous → 401; only the
  caller's apps (another user's `app` → 404 `app_not_found`); breakdown by `endpoint` and `app`;
  rows with < 3 listeners → `"<3"` and no `other`; `unique_end_users` metric.
- [ ] **Step 2–4:** run, implement, run. Commit `feat(usage): serve developer usage reports with a privacy floor`.

### Task 6: Public gallery counts behind `PUBLIC_USAGE_COUNTS_ENABLED`

**Files:** Modify `apps/usage_tracking/api/internal/usage_reports.py`, `config/settings/base.py`;
test `apps/usage_tracking/tests/test_public_usage_counts.py`.

- [ ] **Step 1: Failing tests** — flag off → 404 `usage_counts_disabled`; flag on → rounded
  counts; tenant-restricted asset → 404 `not_found`; second call served from cache.
- [ ] **Step 2–4:** run, implement, run. Commit `feat(usage): expose public usage counts behind a flag`.

### Task 7: Settings, CI/CD, translations, docs, spec §20, performance

- [ ] Settings in `config/settings/base.py`, `env.example`, `deployment/docker/env.template`,
  `.github/workflows/ci-cd.yml` (`vars.STAGING_X || 'default'`, `vars.PROD_X || 'default'`),
  README table. Commit `ci(usage): wire the usage report settings into env files and deploys`.
- [ ] `makemessages`, Arabic for every new string, `msgfmt --check --statistics` → 0
  untranslated. Commit `feat(usage): translate usage report messages to Arabic`.
- [ ] `docs/ARCHITECTURE.md` usage section, spec §20 amendments, backlog minors.
  Commit `docs(usage): document the usage reports API`.
- [ ] Performance: 50k events over 30 days rolled up; time each endpoint cold/warm and record
  query counts in the PR.
- [ ] Full suite + `makemigrations --check`.
