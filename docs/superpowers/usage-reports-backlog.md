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
