# Backend (Django + DRF)

- APIs via DRF; custom Angular Admin (no Wagtail).
- Auth: Auth0 (OIDC/JWKS verification).
- Search: Meilisearch via Celery on Django signals.
- Storage: MinIO (dev) / Alibaba OSS (prod) using django-storages.
- DB: PostgreSQL with UUID PKs, soft deletes, i18n.

## Dev
- Python 3.12+, pip/pipenv/uv
- Env: copy `.env.example` to `.env`

### Commands (suggested)
- run: `python manage.py runserver`
- migrate: `python manage.py migrate`
- test: `pytest`
- worker: `celery -A project worker -l info`

## Notes
- Schema source of truth: `docs/db-design/er-diagram.mmd`.
- Follow Prompt Structure Protocol in `.cursor/rules/cms-v1.mdc`.
