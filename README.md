## Itqan CMS — Quranic Content Management System


Itqan CMS helps Quranic data publishers distribute high-quality, licensed content while enabling developers to integrate it reliably across apps and platforms.

## Goals
- Empower publishers to upload, manage, and govern Quranic resources with versioning and clear licensing.
- Provide developers with standardized, well-documented access via download, APIs, and packages.
- Maintain authenticity and consistency across formats (audio, text, tafsir, translation).
- Foster a collaborative, open-source ecosystem that advances Quranic accessibility.

## Main Features
- **Content publishing**: Upload and manage Quranic resources with metadata, categories, and ownership.
- **Licensing & versioning**: Attach clear licenses (e.g., Creative Commons) and maintain version history.
- **Access control**: Govern who can view, download, or integrate specific assets.
- **Developer APIs**: Clean REST APIs with documentation for easy integration.
- **File/resource distribution**: Offer standardized downloads and resource endpoints.
- **Usage & analytics**: Track access and usage patterns to inform curation and scaling.
- **Admin & workflows**: Robust admin tools and flows to review, publish, and maintain content quality.
- **Internationalization**: Support multilingual descriptions and metadata.
- **Extensible architecture**: Modular apps-based design for new content types and integrations.

## Architecture / Tech Stack

- **Backend**: Django + Django Ninja (Python 3.13+)
- **Dependency Management**: [uv](https://docs.astral.sh/uv/)
- **Database**: PostgreSQL
- **Containerization**: Docker & Docker Compose
- **CI/CD**: GitHub Actions
- **Linting**: pre-commit hooks (enforced on all PRs)
- **Hosting/Infra**: DigitalOcean (e.g., Droplets, Managed PostgreSQL)

## API Architecture

Itqan CMS exposes **four distinct APIs**, each serving a different audience and purpose. All APIs are built with Django Ninja.

### 1. CMS API (Internal API)

- **Mount**: `cms-api/`
- **Purpose**: The internal API powering our frontend web application. Through this API, users ("the developers") can create accounts, log in, explore the platform, and create OAuth applications for themselves.
- **Authentication**: django-allauth (JWT) with social login support (Google/GitHub)
- **Audience**: Registered platform users interacting through the CMS frontend

### 2. Public API (Developers' API)

- **Mount**: `/` (root)
- **Purpose**: The public-facing API consumed by external developers. After a developer creates an OAuth application through the CMS API, they use the Public API to access Quranic content in their own web apps, mobile apps, and other clients. **This is where we expect the majority of traffic** as adoption grows.
- **Authentication**: django-oauth-toolkit (OAuth2 client credentials flow)
- **Audience**: External developer applications

### 3. Tenant API

- **Mount**: `tenant/`
- **Purpose**: A multi-tenant SaaS API for one of our core stakeholders -- **the publishers**. Each publisher can have their own domain and serve content filtered to show only the data they have uploaded, hiding everyone else's. Traffic is differentiated by the `Domain` header. All tenants share a single database; this architecture will not change in the near term.
- **Authentication**: JWT/Session authentication
- **Audience**: Publisher-branded frontend applications

### 4. Portal API

- **Mount**: `portal/`
- **Purpose**: The internal admin portal for uploading, writing, updating, and managing content. Supports full CRUD operations. Relies on a permission system; all users of this API are expected to be company staff. The focus is on heavy lifting and functionality rather than aesthetics.
- **Authentication**: JWT/Session authentication with role-based permissions
- **Audience**: Internal company staff and admins

### API Summary

| API | Mount | Audience | Auth | Traffic Profile |
|-----|-------|----------|------|-----------------|
| **CMS API** | `cms-api/` | Platform users | allauth (JWT) | Moderate |
| **Public API** | `/` | External developers | OAuth2 | High (primary) |
| **Tenant API** | `tenant/` | Publisher domains | JWT/Session | Varies per tenant |
| **Portal API** | `portal/` | Internal staff | JWT/Session + permissions | Low |

For detailed authentication flows, security practices, and developer guides, see [docs/AUTHENTICATION.md](./docs/AUTHENTICATION.md).

### Unified Error Handling

All APIs return errors using the same structure, ensuring a consistent developer experience regardless of which API is consumed:

```python
class ItqanError(Exception):
    def __init__(self, error_name: str, message: str, status_code: int = 400, extra=None):
        """
        error_name: a unique name for the error, must not contain spaces
        message: a human-readable message (should be localized)
        """

class NinjaErrorResponse[ERROR_NAME, EXTRA_TYPE](Schema):
    error_name: ERROR_NAME
    message: str
    extra: EXTRA_TYPE | None = None
```

Example error response:

```json
{
  "error_name": "resource_not_found",
  "message": "The requested resource does not exist.",
  "extra": null
}
```


## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for native setup)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### 1) Clone & Environment

```bash
git clone https://github.com/Itqan-community/cms-backend.git
cd cms-backend

# Native dev env
cp env.example .env

# Docker env (used by compose)
cp deployment/docker/env.template deployment/docker/.env
# edit deployment/docker/.env with your DB_*, SECRET_KEY, and SITE_DOMAIN
```

### 2) Start with Docker (recommended)

```bash
# Start services (web + caddy)
docker compose -f docker-compose.local.yml up -d

# Check status
docker compose -f docker-compose.local.yml ps

# Tail logs
docker compose -f docker-compose.local.yml logs -f web
```

### 3) Native Development (alternative)

```bash
uv sync --group dev
source .venv/bin/activate
pre-commit install

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

> **Note**: `pre-commit install` sets up Git hooks that run linting checks before each commit.
> All PRs must pass linting to be merged.

### 4) Access

- API Docs: http://localhost:8000/docs/
- Health check: http://localhost:8000/health/
- Django Admin: http://localhost:8000/django-admin/

## Project Structure

```
cms-backend/
├── apps/
│   ├── core/                # Shared utilities, error handling, pagination
│   │   ├── ninja_utils/     # ItqanError, NinjaErrorResponse, etc.
│   │   └── ...
│   ├── content/
│   │   ├── api/
│   │   │   ├── internal/    # CMS API endpoints
│   │   │   ├── public/      # Public (Developers') API endpoints
│   │   │   ├── tenant/      # Tenant API endpoints
│   │   │   └── portal/      # Portal API endpoints
│   │   ├── models.py
│   │   ├── services/
│   │   └── tests/
│   ├── users/
│   │   ├── api/
│   │   │   ├── internal/
│   │   │   ├── public/
│   │   │   ├── tenant/
│   │   │   └── portal/
│   │   ├── models.py
│   │   └── tests/
│   └── publishers/
│       ├── api/
│       │   ├── internal/
│       │   ├── public/
│       │   ├── tenant/
│       │   └── portal/
│       ├── models.py
│       └── tests/
├── config/
│   ├── settings/            # base.py, development.py, staging.py, production.py
│   ├── cms_api.py           # CMS API (internal) Ninja config
│   ├── developers_api.py    # Public API Ninja config
│   ├── tenant_api.py        # Tenant API Ninja config
│   ├── portal_api.py        # Portal API Ninja config
│   └── urls.py              # Root URL mounting for all APIs
├── deployment/
│   └── docker/              # Dockerfile, compose, Caddyfile, env.template
├── pyproject.toml
├── uv.lock
├── manage.py
└── ...
```

Each app contains an `api/` directory with subdirectories per API surface (`internal/`, `public/`, `tenant/`, `portal/`). Each API surface has its own tests.



## Documentation

- **[Documentation Index](./docs/)** — Overview of all available documentation
- **[Architecture Guide](./docs/ARCHITECTURE.md)** — System architecture, domain models, and component interactions
- **[Authentication Guide](./docs/AUTHENTICATION.md)** — Complete OAuth flows, security practices, and developer guides
- **[Contributing Guide](./CONTRIBUTING.md)** — How to contribute to the project

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

**Quick Summary:**
- `main` and `staging`: PR-only (no direct commits)
- Flow: `feature branch`→ `staging` (PR) → `main` (PR)
- Start all changes from `staging` or feature branches


## Deployment

Containerized deployment uses Caddy (TLS, static) and the Django app container. See `deployment/docker/README.md` for end-to-end steps (environment variables, logs, and health checks). Database is typically a managed PostgreSQL instance; configure `DB_*` env vars accordingly.

## Security Notes

- Use strong unique `SECRET_KEY` per environment; keep it out of VCS
- CORS/CSRF configured per environment settings
- OAuth `client_secret` must be kept secure (see [docs/AUTHENTICATION.md](./docs/AUTHENTICATION.md))
- JWT tokens via SimpleJWT for `cms-api`, `tenant/`, and `portal/`; OAuth2 via django-oauth-toolkit for the Public API

## License

MIT License. See `LICENSE` for details.

---

Built with care by Itqan Community
