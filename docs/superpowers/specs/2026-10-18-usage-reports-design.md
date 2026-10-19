# Usage Reports — Design

**Status:** approved in brainstorming on 2026-10-18; awaiting written-spec review.
**Repos:** `itqan-cms-backend` (this spec), `cms-frontend`, `itqan-cli`. Each change ships as its own PR
from a `feat/usage-reports*` worktree branched off `origin/staging` (CLI: off `origin/main`).
**Supersedes:** `2026-10-13-asset-download-stats-design.md` (its GraphQL sync, tables and
`/portal/usage/downloads/*` endpoints are replaced; they keep running until cutover).

## 1. Goal

Show publishers, Itqan admins, developers and (optionally) the public how Itqan assets are used,
capturing as much of the real traffic as possible across every distribution channel.

Assets are open and free, so the reports measure **reach** (countries, unique listeners and
downloaders, integrating apps), **adoption** (installs, version adoption) and **engagement**
(plays, surahs, listening times) — not revenue.

Success criteria:

- Every request for an asset file or asset API endpoint through Cloudflare is counted, unsampled,
  including Cloudflare cache hits.
- Gallery downloads, CLI installs and asset views that do not show up in Cloudflare logs are
  counted from Django events.
- R2 reads that bypass both are measured as "unseen traffic", so the gap is known.
- Plays/downloads can be attributed to the integrating app when it uses an API key.
- Unique listeners can be counted over any date range, not only per day.
- Four surfaces: publisher portal, Itqan admin, public gallery counts (behind a flag), developer
  account page.

## 2. Decisions taken in brainstorming

| Topic | Decision |
|---|---|
| Scope | All three phases in one spec: reports on current data, channel/platform attribution, per-app attribution |
| Collection | **Cloudflare Logpush → R2 → hourly import** (rejected: extending the GraphQL sync — sampled, misses headers; a Worker in front of storage — puts our code in the playback path) |
| Extra source | R2 operations analytics (per-object reads) as a reconciliation check |
| Unique identity | **Option C:** stable `HMAC(USAGE_IDENTITY_KEY, ip + user_agent)` for listeners, plus hashed `X-External-User-Id` per app when sent. Raw IPs are never stored by the new pipeline |
| Surfaces | Publisher portal, Itqan admin, public gallery counts (**behind `PUBLIC_USAGE_COUNTS_ENABLED`, default off**), developer usage page |
| Chart library | Apache ECharts via `ngx-echarts` |
| Disclaimers | Shown on every report: counts are lower bounds (local caching and re-hosting are invisible); uniques are estimates |
| Mixpanel | Removed at cutover together with the GraphQL sync and the board-url endpoint |
| Cloudflare changes | Performed by the user in the dashboard, step by step, when the plan asks |
| Cost | Small R2/Logpush costs are acceptable if they improve coverage |

## 3. What is measurable today (findings, 2026-10-15)

From production traffic on `storage.cms.itqan.dev` (7 days, ~9.7k asset requests) and the code:

| Channel | Today | Gap closed by |
|---|---|---|
| Apps/sites streaming recitations | Edge requests (GraphQL sync) | 96% are Android `Dalvik`, then iOS `AppleCoreMedia` (130), browsers (131), Flutter `just_audio` (19), curl (55); **no referers**. App identity comes from the `?c=` tag (§5.2) |
| itqan CLI | File fetches look like `python-requests` (CLI sets its User-Agent only on API calls); `resolve` is not counted | CLI release (§8); Django resolve events (§5.3) |
| Gallery download | `content.UsageEvent` row, but the file is served by a **presigned R2 S3 URL that bypasses the custom domain** | `?download=` links on the custom domain for open assets (§5.4); Django event for restricted ones |
| Public API | Nothing per client; responses are **edge-cached for 300 s**, so Django sees only misses | Logpush on `api.cms.itqan.dev` with custom header fields (§4) |

Zone plan: **Pro**. Logpush is available on Pro (25 GB/account/month included, $0.03/GB beyond for
R2 destinations). The `http_requests` field list is readable for the zone. Custom fields are not
documented as plan-restricted; confirmed at setup (fallback in §4.3).

## 4. Collection

```
storage.cms.itqan.dev ─┐
api.cms.itqan.dev ─────┴─► Logpush (http_requests) ─► R2 itqan-usage-logs/http/<env>/<date>/*.log.gz
                                                            └─► hourly import ─┐
R2 operations analytics (GraphQL, per object/hour) ─► hourly import ───────────┤
Django content.UsageEvent + new CLI resolve events ─► hourly fold-in ──────────┴─► TrafficEvent ─► rollups
```

### 4.1 Logpush job

- Dataset `http_requests`, destination R2 bucket `itqan-usage-logs` (created), output NDJSON gzip.
- **Two jobs**, so each environment reads only its own files:
  - staging: filter `ClientRequestHost in {staging.storage.cms.itqan.dev, staging.api.cms.itqan.dev}`,
    prefix `http/staging/{DATE}/`;
  - production: filter `ClientRequestHost in {storage.cms.itqan.dev, api.cms.itqan.dev}`, prefix
    `http/production/{DATE}/`.
- Fields: `EdgeStartTimestamp`, `RayID`, `ClientRequestHost`, `ClientRequestMethod`,
  `ClientRequestPath`, `ClientRequestURI` (query string), `EdgeResponseStatus`,
  `EdgeResponseBytes`, `CacheCacheStatus`, `ClientIP`, `ClientCountry`, `ClientRequestUserAgent`,
  `ClientRequestReferer`, plus custom request-header fields `x-client-name`, `x-client-version`,
  `x-external-user-id`, `x-itqan-install-id`.
- **Never logged:** `x-api-key`, `authorization`, cookies.
- R2 lifecycle rule on the bucket: delete objects older than 730 days.

### 4.2 Importer (`ENABLE_USAGE_LOGPUSH_IMPORT`)

- Hourly Celery task (minute 10). Lists new objects under the prefix using the R2 read
  credentials, streams each file, parses lines, and inserts `TrafficEvent` rows.
- Idempotent: `LogFileImport(key unique, rows, imported_at)` records every loaded file; a file is
  loaded in one transaction together with its `LogFileImport` row. `TrafficEvent.ray_id` stays
  unique (`ignore_conflicts`), so a re-pushed file cannot double-count.
- After loading, every hour touched by the new events is rebuilt (delete-and-insert per hour, as
  in the current sync), including the play/download sessionization with 5 minutes of context
  before the hour.
- Missed runs catch up: the listing is driven by what is not yet in `LogFileImport`, not by time.
- Advisory lock prevents overlapping runs; the lock is always released (`try/finally`).
- Raw IPs are hashed in memory and never written.

### 4.3 Fallback if custom header fields are unavailable on Pro

Django records `X-Client-Name`, `X-Client-Version` and hashed `X-External-User-Id` on public-API
cache misses (`TrafficEvent` with `source=django`). Because API responses are cached per API key
(§5.2), each app still produces regular misses, so per-app API counts remain available as
lower bounds. Edge rows for the same requests are kept for totals.

### 4.4 R2 reconciliation (`ENABLE_USAGE_R2_RECONCILIATION`)

Hourly, query `r2OperationsAdaptiveGroups` (dimensions `objectName`, `actionType`,
`responseStatusCode`, `datetimeHour`) for `GetObject` on the assets bucket, map object names to
assets with the existing path parser, and store `R2ObjectReadsHourly`. "Unseen traffic" per asset
and hour = R2 reads − edge-seen requests for the same objects (floored at 0). Admin-only.

### 4.5 Cutover

The 2026-10-13 GraphQL sync keeps running until Logpush totals match it within ±1% per hour for
7 consecutive days on production. Then the GraphQL sync, its tables (`AssetDownloadEvent`,
`AssetDownloadHourly`, `AssetDownloadDaily`, `UsageSyncState`), the Mixpanel sync, the board-url
endpoint and the frontend Mixpanel tab are removed in one PR per repo.

## 5. Attribution

### 5.1 Channel and platform

Each event gets exactly one **channel**, first match wins:

| Channel | Rule |
|---|---|
| `gallery` | `kind=gallery_download` (edge `?download=` or Django event) |
| `cli` | User-Agent starts with `itqan-cli/` or `x-itqan-install-id` present |
| `app_identified` | `?c=<slug>` on storage requests, or a resolved `x-client-name`/API key on API requests |
| `web` | Browser User-Agent (`Mozilla/…` without an app token) |
| `app_unidentified` | Media-player/app User-Agents: `Dalvik`, `ExoPlayer`, `okhttp`, `AppleCoreMedia`, `CFNetwork`, `just_audio`, `Dart` |
| `script` | `curl`, `wget`, `python-requests`, `node`, `Go-http-client`, empty |
| `other` | anything else |

**Platform:** `android`, `ios`, `web`, `desktop`, `server`, `unknown` from the User-Agent.

**Bots:** user agents matching a maintained bot list (`bot`, `spider`, `crawler`, known scanners)
or requests for non-asset paths are stored with `is_bot=true` and excluded from every count;
4xx/5xx are stored with their status class and excluded from plays/downloads.

### 5.2 Per-app tagging

- New `APIKey.public_slug` (unique, `[a-z0-9-]{3,40}`, generated from the key name, editable by
  the owner, shown on the API keys page). OAuth applications get the same field.
- Public API responses that contain asset file URLs append `?c=<public_slug>` when the request was
  authenticated with an API key or OAuth app. Unauthenticated requests are untagged.
- Cloudflare **cache rules** (user step): storage cache key ignores the `c` and `download` query
  parameters; API responses use a cache key that includes the `X-API-Key` header, so one app never
  receives another app's tagged URLs.
- An unknown or revoked slug is stored as `app_unidentified` with the raw slug kept for admin
  debugging.

### 5.3 Django events

| Event | Source | Notes |
|---|---|---|
| Gallery download (restricted asset) | existing `content.UsageEvent(file_download)` | Open assets are counted from the edge instead; the fold-in skips open assets to avoid double counts |
| CLI resolve/install | **new** event in `PackageRegistryService` resolve | One per resolved package: asset, version, language, CLI version (UA), hashed install id |
| Asset view | existing `content.UsageEvent(view)` | Shown as "views" and the views → downloads ratio |

The hourly fold-in copies new Django events into `TrafficEvent` (`source=django`, id
`django:<pk>` in `ray_id`), so all reports read one table.

### 5.4 Gallery downloads through the custom domain

`assets/{id}/download/` returns, for open-access assets,
`https://<storage host>/<key>?download=<filename>`. A Cloudflare **transform rule** (user step)
adds `Content-Disposition: attachment; filename="<download value>"` when `download` is present.
Restricted assets keep presigned URLs. The existing `UsageEvent` row is still written.

## 6. Identity

- `listener_id = HMAC-SHA256(USAGE_IDENTITY_KEY, client_ip + "|" + user_agent)` (hex, 64 chars).
  The key never rotates; it defaults to a value derived from `SECRET_KEY` with a startup warning
  recommending an explicit key, because rotating `SECRET_KEY` would reset all unique counts.
- `end_user_id = HMAC-SHA256(USAGE_IDENTITY_KEY, app_id + "|" + external_user_id)` when an
  authenticated API request carries `X-External-User-Id`.
- `install_id = HMAC-SHA256(USAGE_IDENTITY_KEY, x-itqan-install-id)`.
- Labelled in the UI as estimates: shared networks (mobile CGNAT, offices) merge people; changing
  networks split one person.
- **Privacy floor:** in the public and developer scopes, a breakdown row with fewer than 3
  unique listeners is returned as `"<3"` instead of a number.

## 7. Data model (`apps/usage_tracking`)

| Model | Fields / purpose |
|---|---|
| `TrafficEvent` | `ray_id` (unique), `occurred_at`, `source` (`edge`/`django`), `host_env` (`production`/`staging`), `kind` (`audio_surah`, `audio_ayah`, `version_file`, `gallery_download`, `api_call`, `cli_install`, `view`), `asset_id`, `surah`, `asset_version_id`, `language`, `country`, `channel`, `platform`, `app_id` (nullable FK → `APIKey`), `app_slug_raw`, `status_class`, `bytes`, `cache_status`, `listener_id`, `end_user_id`, `install_id`, `ua_family`, `client_name`, `client_version`, `endpoint` (API route template), `is_bot`. Indexes: `(occurred_at)` BRIN, `(asset_id, occurred_at)`, `(app_id, occurred_at)` |
| `TrafficHourly` / `TrafficDaily` | `hour`/`day` × dims (`asset_id`, `kind`, `surah`, `asset_version_id`, `language`, `country`, `channel`, `platform`, `app_id`) with `requests`, `bytes`, `sessions` (plays/downloads/installs by kind), `unique_listeners`. Unique constraint over all dims (`nulls_distinct=False`, Postgres 17) |
| `TrafficMonthlyUniques` | `month` × scope (`asset`, `publisher`, `app`) × `scope_id` × measure (`listeners`, `downloaders`, `installs`, `end_users`) → `count`. Kept forever |
| `R2ObjectReadsHourly` | `hour`, `object_key`, `asset_id`, `reads`, `edge_requests` |
| `LogFileImport` | `key` (unique), `rows`, `imported_at` |
| `UsageImportState` | per importer: `watermark`, `last_run_at`, `last_error` |

Retention: `TrafficEvent` rows older than `USAGE_EVENT_RETENTION_MONTHS` (25) are purged nightly;
rollups and monthly uniques are kept forever; R2 log files allow a rebuild for 730 days.
Volume estimate: tens of millions of rows at most; no partitioning.

## 8. Metrics

| Metric | Definition |
|---|---|
| Request | Non-bot edge request for an asset file or asset API endpoint |
| Play (audio kinds) | A listener's first 200/206 request for a file after ≥ 5 minutes without one (`ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES`) |
| Download (`version_file`, `gallery_download`) | Same sessionization as plays |
| Install | Distinct (`install_id`, `asset_version_id`) per UTC day from `cli_install` events. **Update** = install of a newer version by an `install_id` that had an older version of the same asset |
| API call | 2xx `api_call` for an endpoint that identifies an asset, including edge cache hits. Calls without an asset (lists, search) appear only in the admin and developer scopes |
| Unique listeners / downloaders | Distinct `listener_id` in range (audio kinds / file kinds) |
| Unique end users | Distinct `end_user_id` per app |
| Integrating apps | Distinct identified apps with ≥ 1 play, download or API call in range, plus one "Unidentified apps" bucket |
| Version adoption | Each version's share of downloads + installs in range; headline "% on latest version" |
| Unseen traffic | R2 reads − edge requests (admin only) |
| Estimated completion (later) | Bytes per play ÷ object size; ships after the main reports, labelled as an estimate |

Headline metric per category:

| Category | Headline |
|---|---|
| Recitation | Plays, unique listeners, top surahs, integrating apps, countries, platforms |
| Tafsir, translation, linguistic, tajweed | Downloads + installs, unique downloaders, % on latest version, per-language split, channels, countries |
| Mushaf, font, search, program | Downloads + installs, unique downloaders, % on latest version, channels, platforms |

## 9. Reports API

One query engine; four scopes share `summary/`, `timeseries/`, `breakdown/`.

- **Parameters:** `start_date`, `end_date` (inclusive UTC days; hourly ≤ 31 days; any range ≤ 3660
  days), `granularity` (`hour`/`day`/`week`/`month`), `metric` (`plays`, `downloads`, `installs`,
  `api_calls`, `requests`, `bytes`, `unique_listeners`, `unique_downloaders`, `unique_end_users`,
  `views`), filters (`asset_id`, `category`, `kind`, `channel`, `platform`, `app`, `country`,
  `language`, `version_id`, `surah`), `compare=previous_period`, `tz` (hour-of-week heatmap only).
- `summary/` — headline numbers for the filters + previous-period deltas, metric definitions,
  disclaimers, `data_updated_at`.
- `timeseries/` — zero-filled; `split_by=<dimension>` with top-N (default 8) + "Other".
- `breakdown/` — `by` = asset, surah, country, channel, platform, app, version, language,
  hour_of_week.

| Scope | Path prefix | Access | Extras |
|---|---|---|---|
| Publisher | `/portal/usage/` | `PORTAL_READ_USAGE`, tenant-scoped (existing rules) | `export/` CSV |
| Itqan admin | `/admin/usage/` | Itqan staff | optional `publisher_id`; `leaderboard/` (publishers or assets); `reconciliation/`; CSV |
| Public | `GET /assets/{id}/usage-counts/` (internal API) | anyone | all-time plays, downloads, apps (rounded); cached 1 h; **404 unless `PUBLIC_USAGE_COUNTS_ENABLED=True`** |
| Developer | `/developers/usage/` (account) | signed-in key owner | always filtered to the caller's apps; breakdowns by app, asset, endpoint; unique end users |

Errors (localized): `invalid_range`, `range_too_large`, `invalid_metric_for_kind`,
`asset_not_found`. Responses cached 10 minutes per parameter set. Totals and series read rollups;
only unique metrics read `TrafficEvent` (beyond retention: `TrafficMonthlyUniques`).
The 2026-10-13 `/portal/usage/downloads/*` endpoints have no consumers and are removed when the
new endpoints ship.

## 10. Frontend (`cms-frontend`)

- **Libraries:** `echarts@6.1.0`, `ngx-echarts@20.0.2` (Angular 20 compatible; 22.x needs Angular
  22). Tree-shaken core (line, bar, pie, heatmap, map), loaded only on usage routes. Recorded in
  `PROJECT_MAP.md`.
- World GeoJSON in `public/`, loaded lazily; country names from `Intl.DisplayNames`; numbers from
  `Intl.NumberFormat` (compact) in the active language.
- **Pages:**
  - *Admin → Usage* (existing route): publisher dashboard; Itqan admins also get a publisher picker,
    *Leaderboard* and *Unseen traffic* tabs; the Mixpanel iframe becomes a *Legacy board* tab until
    cutover.
  - *Usage* tab on each asset admin page — one shared component configured per category (§8).
  - *Gallery asset page* — "plays · downloads · apps" line, rendered only when the endpoint returns
    200.
  - *Account → API usage* next to *API keys*; *API keys* page shows and edits `public_slug`.
- **Dashboard layout:** filter bar (presets 7d/30d/90d/12m/custom, category, asset, channel,
  platform, country, Export CSV; state in URL query params) → headline cards with % change →
  trend chart (metric switcher, split by) → channel and platform donuts, world map + country
  table, top assets (AG Grid), integrating apps → footer with *Last updated* and the disclaimer.
- **Asset tab per category:** recitation (plays/listeners trend, 114-surah heatmap, surah vs ayah,
  hour × weekday heatmap in viewer time zone, apps, countries, platforms); tafsir/translation/
  linguistic/tajweed (downloads + installs trend, version adoption stacked area, per-language,
  channels, countries); mushaf/font/search/program (same without per-language, plus platforms).
- **Shared:** one `UsageApiService` with a scope argument; pure chart option builders (one per
  chart type) with unit tests; RTL in Arabic (inverse time axis, y-axis on the right, right-aligned
  legend/tooltip); light/dark ECharts themes from CSS variables; every chart has *View as table*,
  loading, empty and error states; all strings in `en.json` and `ar.json`, including metric
  definitions.

## 11. itqan-cli (release 0.4.0)

- `User-Agent: itqan-cli/<version>` on every request, including file downloads.
- `X-Itqan-Install-Id: <uuid4>` created on first run in `config_dir()/install-id`.
- Not sent when `DO_NOT_TRACK=1` or `ITQAN_NO_TELEMETRY=1`.
- README: two-line disclosure. Released through the normal flow (PyPI, npm, pub.dev, Homebrew).

## 12. Cloudflare steps (performed by the user when the plan asks)

1. ~~Create bucket `itqan-usage-logs`~~ (done). Add lifecycle rule: delete after 730 days.
2. Long-lived account token (created): must include **Account Analytics Read**, **Zone Analytics
   Read** for `itqan.dev`, and **R2 Object Read** on `itqan-usage-logs`. S3 credentials derived
   from it: access key id = token id, secret = SHA-256 of the token value. Stored as GitHub
   secrets; verified from staging without printing it.
3. The two Logpush jobs per §4.1 (staging first, then production), and custom fields for the
   four request headers.
4. Cache rules per §5.2.
5. Transform rule per §5.4.

## 13. Settings (all optional, with defaults; wired into `ci-cd.yml` with `||` defaults)

| Setting | Default |
|---|---|
| `ENABLE_USAGE_LOGPUSH_IMPORT` | `False` |
| `ENABLE_USAGE_R2_RECONCILIATION` | `False` |
| `USAGE_LOGS_BUCKET` | `itqan-usage-logs` |
| `USAGE_LOGS_PREFIX` | `http/production/` (staging sets `http/staging/`) |
| `USAGE_LOGS_ACCESS_KEY_ID`, `USAGE_LOGS_SECRET_ACCESS_KEY` | empty (importer skips with a warning) |
| `USAGE_ANALYTICS_API_TOKEN` | empty → falls back to `CF_API_TOKEN` |
| `CF_ACCOUNT_ID` | empty (reconciliation skips with a warning) |
| `USAGE_IDENTITY_KEY` | derived from `SECRET_KEY` (+ warning) |
| `USAGE_EVENT_RETENTION_MONTHS` | `25` |
| `PUBLIC_USAGE_COUNTS_ENABLED` | `False` |

## 14. Rollout (one PR each; staging first, then production)

| # | Repo | Scope |
|---|---|---|
| 0 | Cloudflare (user) | §12 steps 1–3 for staging hosts; confirm files arrive |
| 1 | Backend | `TrafficEvent` + rollups + import state, Logpush importer, classification, identity, R2 reconciliation, settings, CI/CD wiring |
| 2 | Backend | `public_slug`, `?c=` tagging, gallery `?download=` links, CLI resolve events, Django fold-in; Cloudflare §12 steps 4–5 |
| 3 | Backend | Reports API (four scopes), CSV, public flag; remove `/portal/usage/downloads/*` |
| 4 | Frontend | ECharts setup, dashboard, asset tabs, gallery counts, developer page, `public_slug` on API keys page |
| 5 | CLI | User-Agent + install id, release 0.4.0 |
| 6 | Backend + Frontend | Cutover (§4.5) |

## 15. Testing

- **Backend:** parser and classifier against fixture lines shaped like real traffic (Dalvik,
  AppleCoreMedia, just_audio, browsers, curl, bots, CLI, tagged URLs, missing IP); importer
  idempotency (same file twice, partial/corrupt file, gaps, re-pushed rays); sessionization
  across hour boundaries; installs/updates; uniques and monthly uniques; version adoption;
  reconciliation; each API scope (permissions, tenant isolation, privacy floor, public flag,
  range limits); tagging and cache-key behaviour of the API serializer.
- **Frontend:** option builders (LTR/RTL, empty data), service, each page's loading/empty/error
  states, URL filter state.
- **CLI:** User-Agent on downloads, install id creation/persistence, opt-out variables.
- **Staging end-to-end:** a script plays/downloads tagged and untagged files with varied
  user agents on staging hosts; reports must show exactly that traffic after the next import.
- **Production parity:** §4.5 before cutover.
- Per backend rules: `BaseTestCase`, AAA, `test_<fn>_where_<criteria>_should_<expected>`, Arabic
  catalog at 0 untranslated, docs updated in each PR (`ARCHITECTURE.md`, README, developer API
  docs for `c` and headers, CLI README, frontend `PROJECT_MAP.md`).

## 16. Risks and open items

- Logpush custom fields on Pro — confirmed at step 0; fallback §4.3.
- Account-owned tokens are not listed for Logpush/GraphQL in Cloudflare's compatibility matrix;
  if rejected, a user token is used for that part only.
- Apps that cached old untagged URLs stay `app_unidentified` until they refresh.
- Unique counts are estimates (CGNAT); shown with the disclaimer.
- Changing the API cache key to include `X-API-Key` lowers the API cache hit ratio; acceptable
  at current volume, revisit if origin load rises.

## 17. Out of scope

Estimated completion (listed for later), real-time dashboards (hourly is enough), per-person
tracking beyond the hashed identities above, revenue reporting, and email/scheduled reports.

## 18. Amendments from plan 1 (traffic collection)

1. `TrafficEvent.app_id` is a plain integer, not a foreign key (same reason as `asset_id`).
2. `host_env` is dropped: each environment reads only its own Logpush prefix.
3. Hourly/daily rollups store `requests`, `bytes` and `sessions` only; unique metrics are not
   additive across rows and always come from `TrafficEvent` or `TrafficMonthlyUniques`.
4. `endpoint` is a rollup dimension (developer breakdown by endpoint); events also store `path`.
5. The `app_identified` channel rule and app resolution ship in plan 2; plan 1 stores the raw
   `?c=` value in `app_slug_raw`.
6. `LogFileImport.error` records corrupt files, which are skipped rather than retried.
7. New setting `USAGE_LOGPUSH_MAX_FILES_PER_RUN` (default 500) bounds a catch-up run.
8. On edge rows `end_user_id` hashes `x-client-name` + external id (the edge never sees the API
   key); plan 2's Django fallback hashes `app_id` + external id.
9. Staging and production share one Cloudflare token: the repository-level secrets
   `USAGE_ANALYTICS_API_TOKEN`, `USAGE_LOGS_ACCESS_KEY_ID` and `USAGE_LOGS_SECRET_ACCESS_KEY`
   feed both deploys. Each environment still reads only its own prefix and keeps its own
   `<ENV>_USAGE_IDENTITY_KEY`.

## 19. Amendments from plan 2 (attribution)

1. `UsageApp` (usage_tracking) holds the public slug, one per API key, kept when the key is
   deleted; `APIKey`'s pk is a string while rollups and monthly uniques key apps by integer.
2. No Cloudflare API cache rule: API-key responses are `Cache-Control: private`; Django's Redis
   response caches stay shared because the tag is applied on the way out.
3. API-call attribution uses an `X-Itqan-App` response header captured by a Logpush custom
   response-header field.
4. OAuth apps are not tagged (`ENABLE_OAUTH2=False` everywhere).
5. Parser method rule: files count `GET` only; API routes count `GET` and `POST`.
6. Gallery CDN downloads are behind `GALLERY_DOWNLOADS_VIA_CDN` (default `False`).
7. Django usage events store the `X-Forwarded-For` client IP; the fold-in starts at the newest
   `content.UsageEvent` on its first run.
8. The app slug is cached in Redis per key (cleared on change), keeping warm public-API
   responses query-free.
9. **Cloudflare cache bypass for API-key requests (user step, required with plan 2):** anonymous
   open-asset API responses are edge-cached for 300 s, so a keyed request could get the untagged
   copy. Cache rule on `api.cms.itqan.dev` / `staging.api.cms.itqan.dev`: when the request
   header `x-api-key` is present → *Bypass cache*.
10. Resolves sent with `X-Itqan-Command: outdated` are not counted as installs; the CLI (plan 5)
    sends `X-Itqan-Command: <command>` on registry calls. Older CLIs without the header still
    count every resolve.
11. Gallery CDN download links use `CLOUDFLARE_R2_PUBLIC_BASE_URL` (the custom domain), not
    `file_url.url` (the presigned S3-endpoint URL).

## 20. Amendments from plan 3 (reports API)

1. **Paths.** The root mount is the public developers API, so the admin scope is
   `/portal/admin/usage/…` (Itqan staff = `is_staff`); developer `/cms-api/developers/usage/…`;
   public `/cms-api/assets/{id}/usage-counts/`, with the same asset visibility as
   `/cms-api/assets/{id}/`. Publisher stays `/portal/usage/…`.
2. **Summary** always returns the previous period (same length, immediately before) with a
   `change` ratio. `compare=previous_period` adds an aligned `previous` series to timeseries and
   `previous` values to breakdown rows. `leaderboard/` is a breakdown by `publisher` or `asset`
   with the comparison on. Admin breakdowns and splits also accept `by=publisher`.
3. **Uniques past retention** (range starting before the event-retention cutoff) are the sum of
   `TrafficMonthlyUniques` months (`uniques_basis: "monthly"`), only for filters limited to the
   scope, `asset_id` and `app`; otherwise `null` (`"unavailable"`). Inside retention they are
   exact distincts (`"events"`).
4. **Privacy floor** (developer breakdowns): a row with fewer than 3 distinct listeners in
   retained events returns `"<3"`, and the `other` total is omitted.
5. **Public counts** return `plays`, `downloads` (downloads + CLI installs) and `apps`
   (identified apps with ≥ 1 play, download or API call), floored to two significant figures,
   plus the disclaimers; 404 `usage_counts_disabled` while `PUBLIC_USAGE_COUNTS_ENABLED` is off.
6. **CSV export** (publisher and admin) has one row per period × asset with the additive
   metrics only; unique metrics are not additive across rows.
7. `data_updated_at` = newest error-free run of the Logpush import or the Django fold-in.
8. Split series fold the rest into the key `__other__`; rows without a dimension value (no
   asset, no identified app) use the key `""`.
9. Hour-of-week uses hourly rollups shifted to `tz`; zones with non-hour offsets are bucketed by
   whole hours.
10. Disclaimers are returned as `{code, text}`: `lower_bound`, `uniques_estimated`,
    `hourly_delay`. Metric definitions are localized in `definitions`.
11. New settings: `USAGE_REPORTS_CACHE_SECONDS` (600, `0` disables) and
    `PUBLIC_USAGE_COUNTS_ENABLED` (False). Errors gain `invalid_dimension`, `invalid_timezone`,
    `app_not_found` and `usage_counts_disabled`.
12. The developer page's app filter takes `UsageApp` ids; the options come from a breakdown by
    `app` (apps with traffic in the range).
