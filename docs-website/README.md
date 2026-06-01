# Quranic CMS - Developer Docs — Contributor Guide

Docusaurus 3 site at [docs.cms.itqan.dev](https://docs.cms.itqan.dev). Surfaces the Itqan public APIs in English and Arabic.

---

## Local dev

```bash
npm install

# English (default)
npm run start

# Arabic preview
npm run start:ar
```

> **Note:** API call examples in the guides resolve to `http://localhost:8000` during local dev.
> The **backend must be running at `http://localhost:8000`** for those calls to work.

---

## Project layout

```
docs-website/
├── docs/                        # Hand-written Markdown docs (sidebar-wired)
│   ├── intro.md                 # "Welcome" — first sidebar entry
│   ├── getting-started/
│   │   ├── quickstart.md
│   │   └── authentication.md
│   ├── guides/                  # Conceptual API guides
│   │   ├── api-design.md
│   │   ├── response-structure.md
│   │   ├── pagination.md
│   │   ├── localization.md
│   │   ├── related-resources.md
│   │   ├── recitations-ayah-timings.md
│   │   ├── search-filter-order.md
│   │   └── errors.md
│   └── reference/api/           # GENERATED — gitignored. Created by gen-api-docs.
│                                #  One .api.mdx per OpenAPI operation + sidebar.js.
├── i18n/
│   └── ar/
│       ├── code.json                          # AR translations for <Translate> keys in index.tsx
│       ├── current.json                       # AR translations for doc metadata strings
│       ├── docusaurus-plugin-content-docs/    # AR mirrors of docs/ pages
│       └── docusaurus-theme-classic/
│           ├── navbar.json                    # AR navbar item labels
│           └── footer.json                    # AR footer strings
├── openapi/
│   └── public.json              # OpenAPI 3 spec (exported from Django backend)
│                                #  servers[0] is rewritten at build time by set-api-base-url.mjs
├── scripts/
│   └── set-api-base-url.mjs    # Patches openapi/public.json servers[0] based on DOCS_ENV
├── src/
│   ├── css/
│   │   ├── custom.css           # Global Docusaurus theme overrides and CSS vars
│   │   └── rtl.css              # RTL layout fixes for Arabic locale
│   └── pages/
│       ├── index.tsx            # Marketing landing page (Hero, WhatYouCanBuild,
│       │                        #  ForDevsAndResearchers, WhyItqan, ServeThePurpose)
│       └── index.module.css     # Scoped landing page styles
├── static/
│   └── img/                     # itqan-logo.png — served at root as-is
├── docusaurus.config.ts         # Site URL, locales, navbar, footer, plugins, themes
├── sidebars.ts                  # Sidebar tree — static for guides, dynamic for API reference
├── wrangler.toml                # Cloudflare Pages deploy config (see Deployment section)
└── package.json
```

---

## Editing the landing page

All landing sections live in `src/pages/index.tsx`.

| Section | Component | Policy |
|---|---|---|
| Hero | `Hero` | Refine copy only — no restructure |
| What You Can Build | `WhatYouCanBuild` | Max 4 cards |
| For Devs & Researchers | `ForDevsAndResearchers` | Max 4 bullets per column |
| Why Itqan | `WhyItqan` | Refine copy only — no restructure |
| Help Serve the Purpose | `ServeThePurpose` | CTA before footer |

No animations on landing. Inline SVGs only — no new icon libraries.

---

## Adding or editing a docs page

1. Add or edit the Markdown file under `docs/`.
2. Wire it in `sidebars.ts` if it's a new page.
3. Add an Arabic mirror at `i18n/ar/docusaurus-plugin-content-docs/current/<same-path>.md`.

---

## Translation workflow

EN strings in `src/pages/index.tsx` use `<Translate id="some.key">Fallback text</Translate>`.

For every new or changed EN key:

1. Add the AR entry to `i18n/ar/code.json`:
   ```json
   "some.key": {
     "message": "النص العربي هنا",
     "description": "What this string is"
   }
   ```
2. Verify `npm run start:ar` shows no EN fallback on affected pages.

For full docs pages, add a matching `.md` file under `i18n/ar/docusaurus-plugin-content-docs/current/`.

Navbar and footer AR strings live in `i18n/ar/docusaurus-theme-classic/navbar.json` and `footer.json`.

---

## API base URL mechanism

Guide markdown uses the token `{{API_BASE}}` instead of hardcoded URLs. The remark plugin `scripts/remark-api-base.mjs` substitutes the real URL at build/serve time:

| Condition | Resolved URL |
|---|---|
| `DOCS_ENV=staging` | `https://staging.api.cms.itqan.dev` |
| `DOCS_ENV=production` or default | `https://api.cms.itqan.dev` |
| `npm run start` / `start:ar` (sets `DOCS_ENV=localhost`) | `http://localhost:8000` |

---

## Regenerating API docs

`npm run prebuild` runs two steps automatically:

1. `node scripts/set-api-base-url.mjs` — rewrites `openapi/public.json` `servers[0]` based on `DOCS_ENV` (defaults to `production`).
2. `docusaurus gen-api-docs public` — regenerates `docs/reference/api/` from the spec.

To regenerate manually after a backend change:

```bash
# From the repo root (Django):
python manage.py export_public_openapi --out docs-website/openapi/public.json

# From docs-website/:
npx docusaurus clean-api-docs public
npx docusaurus gen-api-docs public
```

> **Important:** The Token and Revoke endpoint disclaimer text is sourced from the **backend docstrings** in `apps/users/api/public/oauth2.py`. Do not manually edit the generated `.api.mdx` files — those are gitignored and wiped on every regen. Edit the backend docstring, then re-run the export and gen-api-docs steps above.

---

## Build scripts

| Command | What it does |
|---|---|
| `npm run prebuild` | Set API base URL + regenerate API docs (run before any build) |
| `npm run build` | Production build (uses whatever `servers[0]` is in openapi/public.json) |
| `npm run build:staging` | Build with `DOCS_ENV=staging` → staging API base URL |
| `npm run build:prod` | Build with `DOCS_ENV=production` → production API base URL |
| `npm run preview` | Build + serve locally for final check |
| `npm run start` | Dev server (EN, hot reload) |
| `npm run start:ar` | Dev server (AR locale) |

---

## Deployment

- `main` → https://docs.cms.itqan.dev (Cloudflare Pages project: `docs-cms-itqan-dev`)
- `staging` → https://staging.docs.cms.itqan.dev (Cloudflare Pages project: `staging-docs-cms-itqan-dev`)
- PRs touching `docs-website/**` or public API schemas (`apps/**/api/public/**`, `apps/**/schemas.py`) trigger preview deploys at `https://<branch>.<project>.pages.dev`.

Driven entirely by `.github/workflows/docs-deploy.yml`. Path-filtered — irrelevant changes never schedule the workflow.

For local manual deploys (requires `CLOUDFLARE_API_TOKEN` set or `wrangler login`):

```bash
# Production
npm run prebuild
npm run build:prod
npx wrangler pages deploy build --project-name docs-cms-itqan-dev

# Staging
npm run prebuild
DOCS_ENV=staging npm run build:staging
npx wrangler pages deploy build --project-name staging-docs-cms-itqan-dev
```

---

## Common pitfalls

- **RTL**: Arabic text wraps differently. Check card and list layouts in `npm run start:ar` after any landing change.
- **Broken links**: Docusaurus throws on broken internal links (`onBrokenLinks: 'throw'`). Run `npm run build` to catch them.
- **Locale fallback**: If an AR translation key is missing, Docusaurus silently falls back to EN. Always grep new EN keys and confirm each has an AR entry in `i18n/ar/code.json`.
- **Generated files**: Never manually edit files under `docs/reference/api/` — they are gitignored and wiped on every `gen-api-docs` run.
