# Itqan Dependabot — GitHub App Operations (#426)

How the updater authenticates to GitHub, how repositories opt in, and what
it is (and is not) allowed to do. Implementation lives in
`apps/dependabot/`; the manifest contract in `docs/ASSET_MANIFEST.md`.

## 1. GitHub-first V1 decision

V1 supports **GitHub only**. Generic Git hosts (GitLab, Bitbucket, …) are
deferred: there is no host abstraction, no per-host client, and no
multi-host behavior anywhere in the updater.

The decision is enforced, not just documented.
`WatchedRepository.host` stores the host name as metadata for the future,
but a database check constraint (`watched_repository_github_only`) rejects
every other value — including rows created through the ORM, fixtures, or
admin — and the service layer rejects non-`github` hosts before any work.
Lifting this later means: dropping the constraint, adding a client per
host, and recording a new decision here.

## 2. Required GitHub App permissions

For #426 (auth, opt-in, discovery) the App needs exactly:

| Permission | Access | Used for |
|---|---|---|
| Metadata | Read | Repository metadata (`GET /repos/{owner}/{repo}`, default branch) |
| Contents | Read | `itqan-assets.yaml` / `itqan-assets.lock` at the repository root |

**Pull Requests write permission is NOT required for #426** and must not
be requested yet. Discovery is read-only (only `GET`s; the single `POST`
in the codebase is the token exchange). PR write belongs to #427, which
opens and refreshes version-bump PRs.

## 3. Authentication model

Two tokens, two jobs:

- **App JWT** identifies the App itself. Minted locally from App ID + RSA
  private key (RS256), three claims (`iss`, `iat`, `exp`), lifetime capped
  at **10 minutes** (GitHub's maximum). It can only call App-level
  endpoints — it cannot read repositories.
- **Installation token** acts for one installation (the repositories that
  installed the App). Obtained per installation via
  `POST /app/installations/{id}/access_tokens`, valid **~1 hour**, carrying
  only that installation's granted permissions. All repository reads use
  installation tokens, so a leak is confined to one installation and
  expires quickly.

Operational rules:

- Tokens are refreshed before expiry: each cached token is treated as
  expired `GITHUB_TOKEN_CACHE_SKEW_SECONDS` (default 60s) early.
- Tokens live **only in process memory** (per-process cache). They are
  never stored in the database, on disk, or in shared caches.
- The private key, App JWTs, installation tokens, the webhook secret, and
  `Authorization` headers never appear in exceptions, `extra` payloads, or
  logs. Logs carry installation/repository identity, HTTP statuses, and
  expiry timestamps only. Canary-marker tests enforce this.

## 4. Consent flow

1. A repository owner installs the Itqan GitHub App and selects
   repositories. The install selection **is** the consent.
2. GitHub delivers a signed webhook (`X-Hub-Signature-256`, HMAC-SHA-256,
   constant-time compare; missing/invalid signatures are rejected with
   401, payloads are never processed unverified).
3. Listed repositories become `opted_in` (`installation.created`,
   `installation_repositories.added`) — only repositories explicitly
   contained in the event, never anything unlisted.
4. `repositories.removed` flips rows to `opted_out` (rows preserved).
   Uninstall (`installation.deleted`) flips the installation's rows to
   `opted_out`: consent withdrawn, history kept, reinstall re-opts in.
5. `installation.suspend` flips only currently `opted_in` rows to
   `suspended`; `unsuspend` restores only `suspended` rows. An explicitly
   `opted_out` repository is never revived by suspension traffic.
6. Discovery (`ManifestDiscoveryService`) requires the flag on and
   `status == opted_in`, resolves the real default branch, and reads only
   the two root files (`itqan-assets.yaml`, `itqan-assets.lock`),
   classifying them per `docs/ASSET_MANIFEST.md` §5. No writes, no PRs.

Webhook deliveries are idempotent (repeated deliveries change nothing),
unsupported events/actions are acknowledged and ignored, and everything
stays inert while `ENABLE_ITQAN_DEPENDABOT` is `False`.

Delivery deduplication: `X-GitHub-Delivery` GUIDs are stable across
redeliveries, so each verified delivery is recorded once
(`WebhookDelivery`: GUID + event/action only, never payloads or secrets)
in the same transaction as its effects, after they are applied. All
effects are idempotent status flips, so a crash before commit simply
replays cleanly on redelivery.

Known ordering limitation: distinct events carry no reliable ordering
signal — these payloads contain no sequence numbers or timestamps, and
delivery GUIDs are random — so same-installation events apply in arrival
order (GitHub's usual order; only failures/replays reorder). Staleness
across installations is impossible (every write is installation-scoped),
suspend/unsuspend races resolve in a single conditional statement, and any
later legitimate event converges state; discovery itself always reads live
GitHub state. Do not build timestamp watermarks on unverified payload
fields to work around this.

## 5. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ENABLE_ITQAN_DEPENDABOT` | `False` | Master switch; all GitHub traffic stays off until enabled |
| `GITHUB_APP_ID` | `0` | GitHub App ID (positive integer) |
| `GITHUB_APP_PRIVATE_KEY` | `""` | PEM text or path to a PEM file (via `read_file`) |
| `GITHUB_API_BASE_URL` | `https://api.github.com` | API base (https only) |
| `GITHUB_HTTP_TIMEOUT_SECONDS` | `10` | Per-request timeout |
| `GITHUB_TOKEN_CACHE_SKEW_SECONDS` | `60` | Refresh tokens this far before `expires_at` |
| `GITHUB_WEBHOOK_SECRET` | `""` | Webhook signing secret (required to receive deliveries) |

## 6. Maintainer GitHub App registration

1. Create the App (organization settings → Developer settings → GitHub
   Apps → New): name it recognizably (e.g. `Itqan Dependabot`), note the
   App ID → `GITHUB_APP_ID`.
2. Permissions: Metadata **Read**, Contents **Read** — nothing else for
   #426. Do not enable Pull Requests yet.
3. Subscribe to webhook events: `installation`,
   `installation_repositories`. Set the webhook URL to
   `https://<cms-host>/cms-api/dependabot/github/webhook/` and generate a
   signing secret → `GITHUB_WEBHOOK_SECRET`.
4. Generate a private key → `GITHUB_APP_PRIVATE_KEY` (value or file path).
5. Set `ENABLE_ITQAN_DEPENDABOT=True` only when ready to receive traffic.
6. Install the App on a test repository and confirm a `WatchedRepository`
   row appears `opted_in`; remove it and confirm `opted_out`.

## 7. Explicit #427 boundary

#427 (PR automation) owns everything this phase deliberately lacks:

- branch creation in consumer repositories
- lockfile modification or writing
- commits to consumer repositories
- opening version-bump PRs
- refreshing / superseding open PRs
- batching and fan-out over opted-in repositories
- requesting Pull Requests write permission on the GitHub App
