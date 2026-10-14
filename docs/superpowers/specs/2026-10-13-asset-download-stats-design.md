# Asset Download Statistics — Design

**Date:** 2026-10-13
**Status:** Implemented (uncommitted) on `feat/asset-download-stats`
**Repos:** `itqan-cms-backend` (this spec), `cms-frontend` (separate spec, later)

## Problem

Publishers need to see how often their assets are downloaded and played: overall
totals and graphs on a dashboard, and numbers on each asset's detail page.

The only reliable source is Cloudflare's edge. Files are served from R2 through
the `storage.cms.itqan.dev` custom domain behind Cloudflare:

- Django API responses are cached by clients, so counting in Django undercounts.
- R2's own metrics (`r2OperationsAdaptiveGroups`) only see requests that reach the
  bucket, so cache hits — most downloads of popular files — are missing.
- Edge HTTP analytics on the custom domain see every request, cache hits included.

Today `apps/usage_tracking` pulls 6-hour aggregates from Cloudflare GraphQL
(`httpRequestsAdaptiveGroups`) and imports them into Mixpanel; publishers see an
embedded Mixpanel board. That data has no per-request time, only surah tracks are
counted, a missed or failed run loses its window permanently, and rows beyond the
query limit are silently dropped.

## Requirements

1. Count downloads of every downloadable asset file: surah tracks, ayah audio, and
   asset version files.
2. Keep the exact time of each request; graphs at hourly resolution.
3. The sync is idempotent: re-running any period never duplicates or inflates counts.
4. A missed or failed run is covered by subsequent runs, within Cloudflare's
   retention.
5. Expose counts to publishers through the portal API, scoped to their own assets.
6. Distinguish raw requests from plays (a single play produces several requests).
7. All new settings are optional with defaults.
8. The existing Mixpanel sync keeps running unchanged until Mixpanel is retired.

## Non-goals

- Admin cross-publisher views, CSV export, public developer-API exposure.
- Local-timezone day boundaries (days are UTC; see API).
- Near-live data; hourly freshness is enough.
- Prometheus / Grafana for publisher numbers (they stay for internal operations).
- The frontend (dashboard, asset detail numbers, chart library) — separate spec.

## Data source

Cloudflare GraphQL Analytics, zone `CF_ZONE_ID`, host `CF_R2_CUSTOM_DOMAIN`,
`requestSource: "eyeball"`, two queries per hour:

- **`httpRequestsAdaptive`** (individual requests) for exact times and plays.
  Fields: `datetime`, `rayName`, `clientRequestPath`, `clientCountryName`,
  `edgeResponseStatus`, `clientIP`. This dataset does **not** expose bytes or
  `sampleInterval`.
- **`httpRequestsAdaptiveGroups`** grouped by path, country and status for
  `count`, `sum.edgeResponseBytes` and `avg.sampleInterval`. Request counts and
  bytes in the rollups come from here, so they stay correct even if sampling
  kicks in.

Verified against production on 2026-10-13 (10:00–11:00 UTC), using the
`CF_API_TOKEN` from the staging environment:

- `settings.httpRequestsAdaptive`: enabled, `maxPageSize` 10000, `maxDuration`
  30 days, `notOlderThan` 31 days; `clientIP` is readable with this token.
- 96 individual requests, 96 distinct `rayName`s, `clientIP` present on all 96.
- The grouped query returned `count` 96 with `avg.sampleInterval` 1, i.e. the
  data is unsampled at current volume, and 41 path × country × status rows.

Why this dataset:

- Free on every plan, at least 31 days of retention, no setup.
- Returns one row per request with second-level timestamps.
- Current volume (~100k requests/month, ~140/hour) is far below the sampling
  threshold and the 10,000-row page limit, so rows are effectively one per request.
  `sampleInterval` is stored so counts stay correct if sampling ever kicks in.

Alternatives considered and rejected:

| Option | Why not |
|---|---|
| `httpRequestsAdaptiveGroups` (current) | Aggregates only; no per-request time, no play deduplication |
| R2 operation metrics / Prometheus exporters | Miss cache hits; no per-object labels |
| Log Explorer `http_requests` + SQL API | Paid add-on, not enabled; no accuracy gain at this volume |
| Logpush `http_requests` → R2 | No backfill, extra file-processing pipeline; no gain at this volume |
| Worker in front of the domain | New component in the download path |

Limits that apply (from Cloudflare docs): 300 GraphQL queries per 5 minutes;
per-dataset `maxPageSize`, `maxDuration` and `notOlderThan` are read at runtime
from the GraphQL `settings` node.

## Data model (`apps/usage_tracking`)

`apps.usage_tracking` is installed unconditionally; it was previously installed only
when `MIXPANEL_ENABLED`, which would have left these tables missing in CI and local
development. Mixpanel behaviour stays gated by `MIXPANEL_ENABLED`.

Shared column semantics:

- `file_kind`: `surah` | `ayah` | `version`.
- `surah`: set for `surah` and `ayah`, otherwise null.
- `asset_version_id`: set for `version` when the path carries a numeric version id,
  otherwise null (e.g. legacy `versions/tmp-xxxx/` paths).
- `asset_id`: plain integer, **not** a foreign key — deleting an asset must not
  cascade into or block on its history, and the sync must not depend on the asset
  row existing.
- `country`: ISO code as returned by Cloudflare (`XX` when unknown).
- `status_class`: `full` (200) | `partial` (206) | `other`.

Fact tables do not inherit `BaseModel`: `created_at`/`updated_at` per row adds
storage and carries no meaning when rows are replaced by delete-and-insert.

### `AssetDownloadEvent` — one row per request

| Field | Type | Notes |
|---|---|---|
| `ray_id` | char, **unique** | Cloudflare request id; makes re-imports duplicate-free |
| `occurred_at` | datetime | Exact request time, UTC |
| `asset_id` | int | |
| `file_kind` | char | |
| `surah` | smallint, null | |
| `asset_version_id` | int, null | |
| `country` | char(2) | |
| `status_class` | char | |
| `client_hash` | char(64) | HMAC-SHA256 of client IP, key = `SECRET_KEY` + UTC date of the request |

Index: `(asset_id, occurred_at)`; index supporting the play computation:
`(client_hash, asset_id, file_kind, surah, asset_version_id, occurred_at)`.

The raw IP is never stored. The daily key means a client cannot be linked across
days.

Retention: kept forever by default. If `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` is set,
the sync deletes events older than that; rollups are never trimmed.

### `AssetDownloadHourly` — rollup

| Field | Type |
|---|---|
| `hour` | datetime (UTC, start of hour) |
| `asset_id`, `file_kind`, `surah`, `asset_version_id`, `country`, `status_class` | as above |
| `requests` | bigint |
| `bytes` | bigint |
| `plays` | bigint |

Unique: `(hour, asset_id, file_kind, surah, asset_version_id, country, status_class)`
with `nulls_distinct=False` (Django 5.2). Index: `(asset_id, hour)`.

### `AssetDownloadDaily` — rollup

Same as hourly with `day` (date, UTC) instead of `hour`. Derived entirely from the
hourly table and always rebuildable. Index: `(asset_id, day)`.

### `UsageSyncState`

Inherits `BaseModel`. One row per job; key `cf_asset_downloads`.

| Field | Notes |
|---|---|
| `key` | unique |
| `watermark` | every hour before this is fully stored |
| `last_run_at` | |
| `last_error` | text, blank when the last run succeeded |

## Path parsing

Served paths have a `/media/` prefix. Recognised shapes (from `apps/core/uploads.py`):

| Kind | Path |
|---|---|
| `surah` | `/media/uploads/assets/{asset_id}/recitations/{surah:03}.{ext}` |
| `ayah` | `/media/uploads/assets/{asset_id}/recitations/{folder_id}/{surah:03}/ayah_{n:03}.mp3` |
| `version` | `/media/uploads/assets/{asset_id}/versions/{version_id}/{filename}` |

- Surah tracks accept any extension (the upload function keeps the original one).
- Ayah requests are collapsed to their surah; the ayah number is not stored.
- Thumbnails, previews, publisher and reciter images never match and are ignored.
- Unmatched paths are dropped and counted in the run's log line.

## Plays

Only requests that delivered content (`full` 200 / `partial` 206) take part; 404s and
other failures never count as plays. A request **starts a play** unless an earlier request with the same `client_hash`
and the same file (`asset_id`, `file_kind`, `surah`, `asset_version_id`) occurred
no more than **5 minutes** before it. Each request extends the window, so a
continuous listening session is one play.

- A play is credited to the rollup row of its starting request (that request's
  hour, country and status class). Summing `plays` across status classes gives
  total plays.
- Computed in SQL with `LAG(occurred_at)` over the file + client partition. The
  computation for an hour reads the preceding 5 minutes of events as context.
- Plays require unsampled events. If the grouped query reports
  `avg.sampleInterval > 1` for an hour, plays for that hour are still computed
  from the returned events, a warning is logged, and the hour is flagged
  approximate in the log (not expected at current volume).
- Known imprecision, accepted: clients behind a shared IP playing the same file in
  the same window merge into one play; a session crossing UTC midnight counts twice
  because the hash key changes daily.

## Sync job

Celery beat task `sync_asset_downloads_task`, **hourly at minute 20** (offset from
the Mixpanel job at minute 5). Service in `apps/usage_tracking/services/`,
Cloudflare access in a client next to `cf_analytics_client.py`, persistence in a
repository — following the app's existing layering.

### Each run

1. **Guard.** Exit if `ENABLE_ASSET_DOWNLOAD_SYNC` is false or `CF_ZONE_ID`,
   `CF_API_TOKEN`, `CF_R2_CUSTOM_DOMAIN` are missing.
2. **Lock.** `pg_try_advisory_lock`; exit immediately if another run holds it.
3. **Plan slices.** One-hour slices from
   `min(watermark, floor_hour(now) − REFRESH_HOURS)` up to the last hour that ended
   at least `LAG_MINUTES` ago, oldest first, at most `MAX_SLICES_PER_RUN`.
   - No state row yet: start at the oldest hour Cloudflare retains (`notOlderThan`),
     which backfills on the first runs.
   - Watermark older than retention: jump to the oldest retained hour and log an
     error naming the lost range.
4. **Fetch the hour** — events from `httpRequestsAdaptive` and totals from
   `httpRequestsAdaptiveGroups` — with a single path filter
   (`/media/uploads/assets/%`); the parser drops non-download files under that
   prefix (thumbnails, previews). Events are ordered by `datetime`. If a response reaches `maxPageSize`, split the
   range in half and retry, down to 5 minutes; at 5 minutes, keep what was
   returned and report an error to Sentry instead of blocking the sync.
5. **Write the hour in one transaction:**
   1. delete the hour's events and insert the fetched ones (parsed, hashed);
   2. delete and rebuild the hour's hourly rows: `requests` and `bytes` from the
      grouped totals, `plays` from the events;
   3. delete and rebuild that day's daily rows from the hourly table;
   4. advance the watermark to the hour's end (never backwards).
6. **On any error** the hour rolls back, `last_error` is written, the error goes
   to Sentry, and the run stops; the next run resumes from the same hour.
7. **Retention.** If `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` is set, delete older
   events.
8. Write `last_run_at`, clear `last_error`, release the lock.

Re-fetching the last `REFRESH_HOURS` every run picks up late-arriving Cloudflare
data. Because each hour is replaced, never incremented, re-runs are idempotent.

### Staleness alert

Each run logs an error (→ Sentry) when the watermark is more than
`STALE_HOURS` behind `now`.

### Settings (all optional)

| Setting | Default |
|---|---|
| `ENABLE_ASSET_DOWNLOAD_SYNC` | `False` |
| `ASSET_DOWNLOAD_SYNC_LAG_MINUTES` | `15` |
| `ASSET_DOWNLOAD_SYNC_REFRESH_HOURS` | `2` |
| `ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN` | `24` |
| `ASSET_DOWNLOAD_SYNC_STALE_HOURS` | `6` |
| `ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES` | `5` |
| `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` | unset (keep forever) |

Reused, unchanged: `CF_ZONE_ID`, `CF_API_TOKEN`, `CF_R2_CUSTOM_DOMAIN`. The token
needs Zone Analytics Read and access to the `clientIP` field (verified).
`CF_R2_CUSTOM_DOMAIN` is currently **unset on staging**; it must be set there before
enabling the sync.

## Portal API

Added to the existing usage router (`apps/usage_tracking/api/portal/usage.py`,
tag `Usage`). Scoped to the publisher from `X-Tenant`. Requires the new
`PORTAL_READ_USAGE` permission, granted to publisher roles.

Shared query parameters: `start_date`, `end_date` (required, inclusive UTC dates; `from` is a Python keyword), `asset_id`, `file_kind` (optional). `end_date` before `start_date` returns 400 `invalid_range`.
An `asset_id` not owned by the publisher returns 404 `asset_not_found`.

Every response includes `data_until` (the watermark) so the UI can show freshness.

A metrics object is `{requests_full, requests_partial, requests_other, bytes, plays}`.

| Endpoint | Response |
|---|---|
| `GET usage/downloads/summary/` | Metrics per `file_kind` plus a total |
| `GET usage/downloads/timeseries/?granularity=hour\|day\|month&split_by=file_kind\|status_class` | `{series: [{key, points: [{t, ...metrics}]}]}`; without `split_by`, one series with key `all` |
| `GET usage/downloads/breakdown/?by=asset\|surah\|country&limit=` | Top N `{key, label, ...metrics}` |

- **Zero-filled:** time series return every bucket in the range.
- **Table choice:** `granularity=hour` reads the hourly table, capped at 31 days
  (400 `range_too_large`); `day`, `month`, `summary` and `breakdown` read the daily
  table.
- **UTC:** day and month buckets are UTC days. Hourly points can be shown in local
  time by the frontend.
- The API returns raw status-class counts and plays; which number the UI calls
  "downloads" is a frontend decision.

New error messages and the permission label are localized (Arabic) per the repo's
localization gate.

## Mixpanel

The existing `sync_audio_usage_task` is not modified. Retiring Mixpanel later
means deleting that task, its client, the board-url endpoint and the
`mixpanel_board_url` field.

## Testing

All tests use `BaseTestCase`; Sentry is stubbed (`sentry-sdk` is a prod-only
extra). Cloudflare is mocked with recorded GraphQL responses.

- Path parser: every file kind, non-mp3 surah tracks, `tmp-` version paths,
  ignored image paths, unknown paths.
- Client hash: stable within a UTC day, different across days, raw IP never stored.
- Slice planning: watermark, refresh window, lag, per-run cap, first-run backfill,
  retention jump.
- Idempotency: the same hour imported twice yields identical rows; changed
  Cloudflare data replaces rather than adds.
- Truncation: split and merge into one hour; Sentry report at the 5-minute floor.
- Failure: an error mid-hour rolls back and leaves the watermark unchanged; a held
  lock exits.
- Plays: 200+206 pair = 1 play; gap > 5 min = 2 plays; play crossing an hour
  boundary credited to the first hour; different clients = separate plays.
- Rollups: daily equals the sum of hourly, including after an hour is rewritten;
  hourly `requests`/`bytes` come from grouped totals, `plays` from events.
- API: tenant scoping (other publisher's asset → 404), permission enforced,
  zero-fill, `split_by`, 31-day hourly cap, `data_until`.
- Localization: `msgfmt --check --statistics` reports 0 untranslated.

## Rollout

1. Migrations: four tables. The permission row and its grant to `Publisher Member` are created by the existing `post_migrate` handlers.
2. Deploy with the sync disabled; set `CF_R2_CUSTOM_DOMAIN` on staging, then enable
   `ENABLE_ASSET_DOWNLOAD_SYNC` there.
   The first runs backfill up to Cloudflare's retention.
3. Watch staging for a few days: events/hour, table sizes, split frequency, rate
   limit errors, plays vs requests ratio.
4. Enable on production.

## Documentation

- `docs/ARCHITECTURE.md`: new models and the sync flow.
- `deployment/docker/env.template` and `README.md`: new settings.
- `docs-website` unchanged (portal API is not public).

## Risks

- **Permissions conflict:** `apps/core/permissions.py` has uncommitted changes on
  another branch; expect a small rebase conflict.
- **`clientIP` access:** verified on 2026-10-13. If the token is rotated, the new
  one must keep access to `clientIP`, or plays cannot be deduplicated per client.
- **Growth:** at millions of requests/day, `httpRequestsAdaptive` will sample and
  the event table grows fast; set `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` and
  revisit Logpush.
