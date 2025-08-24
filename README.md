## Itqan CMS (Monorepo)

This repository hosts the Itqan CMS platform: Quranic data publishing and consumption.

### Structure (Layout A)
```
frontend/   # Angular 19 app (CSR → SSR later via Angular Universal)
backend/    # Django + DRF API; Admin is a custom Angular app
docs/       # diagrams and requirements
.cursor/    # project rules (see `.cursor/rules/cms-v1.mdc`)
```

### Getting Started
- See `frontend/README.md` and `backend/README.md` for per-app setup.
- Schema source of truth: `docs/db-design/er-diagram.mmd`.


