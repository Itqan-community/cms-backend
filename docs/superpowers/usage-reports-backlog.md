# Usage reports: deferred follow-ups

Minor issues found in the final reviews of the usage-reports plans. None blocks a release;
tackle them once the reports API (plan 3), frontend (plan 4) and CLI headers (plan 5) ship.
Spec: `docs/superpowers/specs/2026-10-18-usage-reports-design.md`.

## From plan 2 (attribution)

- [ ] **Fold-in skips out-of-order rows.** `fold_in_django_events` advances an id cursor, so a
      `UsageEvent` committed with a lower id after the cursor passed it is never copied. Fix: only
      read rows older than ~1 minute, or re-scan a small id window behind the cursor.
- [ ] **Renamed slugs can be reused.** After an app renames its slug, another app can claim the
      old one and old `?c=` URLs get attributed to the new owner. Fix: keep retired slugs reserved
      (history table or `UsageApp.previous_slugs`).
- [ ] **API-key PATCH is not atomic.** The name is saved before a bad `app_slug` is rejected.
      Fix: validate the slug first, or wrap both updates in one transaction.
- [ ] **API-key list is N+1 on `app_slug`.** One query per key. Fix: `select_related("usage_app")`.
- [ ] **Generated slugs can contain `_`**, which then fails the edit validation; two keys created
      at the same moment with the same name can raise a 500 on the unique slug. Fix: slugify to
      `[a-z0-9-]` only and retry on `IntegrityError`.
- [ ] **Non-ASCII storage URLs are not tagged.** JSON escapes them as `\uXXXX`, so the
      `tag_storage_urls` regex stops at the backslash. Fix: tag before serialization, or match
      escaped sequences.
- [ ] **`no-store` becomes `no-cache`** when the tagging middleware marks a keyed response
      private. Fix: keep `no-store` when present.
- [ ] **`X-Forwarded-For` is spoofable at the origin.** Requests that bypass Cloudflare can set
      any client IP. Fix: firewall the origin to Cloudflare IP ranges (or Cloudflare Tunnel).
- [ ] **Fold-in rows have country `XX`.** Django events don't store the country. Fix: save
      `CF-IPCountry` on `UsageEvent` and copy it. Also `FoldInResult.events` counts rows that
      `ignore_conflicts` skipped.
- [ ] **Old CLIs count `itqan outdated` as installs.** Goes away once plan 5's CLI (sends
      `X-Itqan-Command`) is widely adopted.

## From plan 3 (reports API)

- [ ] **API calls include 3xx.** Rollup sessions for `api_call` count every counted status
      (2xx and 3xx); spec §8 says 2xx. Fix in `rebuild_hour` (count `SUCCESS`/`FULL` only).
- [ ] **Hour-of-week for half-hour zones.** Hourly rollups are shifted by whole hours, so
      `Asia/Kolkata` buckets are 30 minutes off. Fix: read events for such zones, or document.
- [ ] **Monthly uniques are summed across months and scopes.** Past retention, a listener active
      in two months (or under two publishers of one member) counts twice. Fix: store yearly
      uniques too, or label the basis in the UI (the API already returns `uniques_basis`).
- [ ] **Privacy floor masks everything past retention.** Developer breakdown rows whose events
      were purged have 0 known listeners and show `"<3"`. Fix: store per-row listener counts in
      the monthly table, or skip the floor for ranges past retention.
- [ ] **Unique splits run three event queries.** Fine at 50k events (≈ 50 ms); revisit with
      production volume.
- [ ] **No cache invalidation.** Reports may lag the hourly import by up to
      `USAGE_REPORTS_CACHE_SECONDS`. Fix: include `data_updated_at` in the cache key if needed.
- [ ] **The publisher-scope publisher list runs on every request**, including cache hits (one
      small query). Fix: cache it with the membership ids.

## Later phase: expiring, signed storage links (after the plan-6 cutover)

Not a defect; a design to pick up once the reports are live. Decided 2026-10-19: do **not**
move assets to R2 presigned URLs. Those bypass `storage.cms.itqan.dev`, so Logpush loses every
play (no country, user agent, uniques or `?c=` app), the CDN cache goes away, long playback
breaks when the link expires mid-listen, and apps can still copy the file while the link is
valid.

Instead, sign links on our own domain and let Cloudflare check them at the edge:

- [ ] **Confirm plan support.** WAF custom rules with `is_timed_hmac_valid_v0` may need a plan
      above Pro; check Cloudflare's docs before committing to it.
- [ ] **Link format.** `https://storage.cms.itqan.dev/media/<path>?c=<slug>&verify=<ts>-<hmac>`.
      The HMAC covers path + `c` + timestamp, so the app slug can't be stripped or swapped (makes
      attribution tamper-proof). The secret lives in settings and the Cloudflare rule only.
- [ ] **Signing in Django.** Extend `tag_storage_urls` (plan 2 middleware) and the gallery CDN
      download link to append `verify`. TTL setting, e.g. `STORAGE_LINK_TTL_HOURS` (6–24 h),
      well above the 300 s API edge cache so cached responses never hand out expired links.
- [ ] **Edge rule.** Block requests on the storage hosts whose `verify` is missing or invalid;
      the cache key ignores `verify` (and `c`, `download`) so CDN hit rates stay the same.
- [ ] **Transition.** Ship signing first with the rule in log-only mode; measure unsigned
      traffic per app in the reports (needs a `signed` flag on `TrafficEvent` or a Logpush
      field), announce a deadline to integrators, then enforce. Existing hard-coded URLs break at
      enforcement.
- [ ] **Limits to state in docs.** Expiry stops reuse of old links, not copying during the
      valid window; device caching stays invisible (the cache disclaimer still applies).
- [ ] **Optional.** A shorter `Cache-Control: max-age` on audio, so well-behaved players
      re-fetch more often; trade-off is bandwidth and offline listening.
