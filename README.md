## Itqan CMS — Quranic Content Management System


Itqan CMS helps Quranic data publishers distribute high-quality, licensed content while enabling developers to integrate it reliably across apps and platforms.

## 🔮 Goals
- Empower publishers to upload, manage, and govern Quranic resources with versioning and clear licensing.
- Provide developers with standardized, well-documented access via download, APIs, and packages.
- Maintain authenticity and consistency across formats (audio, text, tafsir, translation).
- Foster a collaborative, open-source ecosystem that advances Quranic accessibility.

## ✨ Main Features
- **Content publishing**: Upload and manage Quranic resources with metadata, categories, and ownership.
- **Licensing & versioning**: Attach clear licenses (e.g., Creative Commons) and maintain version history.
- **Access control**: Govern who can view, download, or integrate specific assets.
- **Developer APIs**: Clean REST APIs with documentation for easy integration.
- **File/resource distribution**: Offer standardized downloads and resource endpoints.
- **Usage & analytics**: Track access and usage patterns to inform curation and scaling.
- **Admin & workflows**: Robust admin tools and flows to review, publish, and maintain content quality.
- **Internationalization**: Support multilingual descriptions and metadata.
- **Extensible architecture**: Modular apps-based design for new content types and integrations.

## 🏗️ Architecture / Tech Stack

- **Backend**: Django + Django Ninja (Python 3.13+)
- **Database**: PostgreSQL
- **Containerization**: Docker & Docker Compose
- **CI/CD**: GitHub Actions
- **Hosting/Infra**: DigitalOcean (e.g., Droplets, Managed PostgreSQL)

## 🔐 Authentication

Itqan CMS uses **two distinct authentication systems** for different user types:

| User Type | API | Authentication | Documentation |
|-----------|-----|----------------|---------------|
| **Publishers** | `cms-api` | django-allauth (JWT) | Account creation, social login (Google/GitHub) |
| **Developers** | `developers-api` | django-oauth-toolkit (OAuth2) | Client credentials flow |

**📖 For detailed authentication flows, security practices, and developer guides, see [docs/AUTHENTICATION.md](./docs/AUTHENTICATION.md)**


## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.13+ (for native setup)

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

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4) Access

- API Docs: http://localhost:8000/docs/
- Health check: http://localhost:8000/health/
- Django Admin: http://localhost:8000/django-admin/

## 📁 Project Structure

```
cms-backend/
├── apps/
│   ├── core/
│   │   ├── models.py
│   │   ├── views/
│   │   ├── services/
│   │   └── tests/
│   ├── content/
│   │   ├── models.py
│   │   ├── views/
│   │   ├── services/
│   │   └── tests/
│   ├── users/
│   │   ├── models.py
│   │   ├── views/
│   │   └── tests/
│   └── publishers/
│       ├── models.py
│       ├── views/
│       └── tests/
├── config/
│   ├── settings/            # base.py, development.py, staging.py, production.py
│   ├── ninja_urls.py        # API setup and docs
│   └── urls.py              # Root URLs (health, admin, accounts, ninja)
├── deployment/
│   └── docker/              # Dockerfile, compose, Caddyfile, env.template
├── pyproject.toml
├── uv.lock
├── manage.py
└── ...
```



## 📚 Documentation

- **[Documentation Index](./docs/)** — Overview of all available documentation
- **[Architecture Guide](./docs/ARCHITECTURE.md)** — System architecture, domain models, and component interactions
- **[Authentication Guide](./docs/AUTHENTICATION.md)** — Complete OAuth flows, security practices, and developer guides
- **[Contributing Guide](./CONTRIBUTING.md)** — How to contribute to the project

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

**Quick Summary:**
- `main` and `staging`: PR-only (no direct commits)
- Flow: `feature branch`→ `staging` (PR) → `main` (PR)
- Start all changes from `staging` or feature branches


## 🚚 Deployment

Containerized deployment uses Caddy (TLS, static) and the Django app container. See `deployment/docker/README.md` for end-to-end steps (environment variables, logs, and health checks). Database is typically a managed PostgreSQL instance; configure `DB_*` env vars accordingly.

## 🔒 Security Notes

- Use strong unique `SECRET_KEY` per environment; keep it out of VCS
- CORS/CSRF configured per environment settings
- OAuth `client_secret` must be kept secure (see [docs/AUTHENTICATION.md](./docs/AUTHENTICATION.md))
- JWT tokens via SimpleJWT for `cms-api`; OAuth2 via django-oauth-toolkit for `developers-api`

## 📄 License

MIT License. See `LICENSE` for details.

---

Built with ❤️ by Itqan Community
