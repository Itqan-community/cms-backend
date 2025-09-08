# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Itqan CMS** is a Quranic Content Management System backend built with Django. It's designed as a headless CMS to aggregate, license, and distribute verified Quranic content (text, audio, translations, tafsir) to developers and publishers through controlled APIs with proper licensing workflows.

This is the **backend repository only** - the Angular frontend lives in a separate repository.

### Tech Stack

- **Backend**: Django 4.2 LTS + Wagtail CMS + Django REST Framework  
- **Database**: PostgreSQL 16 with UUID primary keys
- **Authentication**: Django Allauth + JWT tokens (Auth0 integration)
- **Search**: MeiliSearch v1.6 for full-text search
- **Cache/Queue**: Redis for caching and Celery task queue
- **Storage**: MinIO (dev) / Alibaba OSS (prod) via django-storages
- **API Documentation**: DRF Spectacular (OpenAPI 3.0)

### Architecture Pattern

The system follows a **publisher-consumer model**:
- **Publishers**: Upload and manage Quranic resources
- **Developers/Consumers**: Request access to licensed content through APIs
- **Reviewers**: Content moderation and quality assurance
- **Admins**: System management and user oversight

## Quick Start Commands

### Development Server
```bash
# Start local development (from project root)
./dev.sh                          # Starts Django on :8000 (requires activated venv in backend/)

# Alternative: Start with Docker services
docker-compose up -d              # PostgreSQL + Redis
cd src && python manage.py runserver 127.0.0.1:8000
```

### Database Management
```bash
cd src
python manage.py migrate              # Run migrations
python manage.py makemigrations       # Create new migrations
python manage.py createsuperuser      # Create admin user

# Database operations with Docker
docker-compose exec postgres psql -U itqan_user -d itqan_cms
```

### Testing
```bash
cd src
python manage.py test                 # Run all tests
python manage.py test apps.accounts   # Run specific app tests

# Test API endpoints directly
curl http://127.0.0.1:8000/health/
curl http://127.0.0.1:8000/api/v1/
```

### Static Files & Media
```bash
cd src
python manage.py collectstatic        # Collect static files
python manage.py shell                # Django shell for debugging
```

### Celery Background Tasks
```bash
cd src
celery -A config worker --loglevel=info      # Start Celery worker
celery -A config beat --loglevel=info        # Start Celery beat (scheduled tasks)
```

## Architecture Overview

### Django Apps Structure

**Core Apps:**
- `apps.accounts` - User management, roles, authentication (custom User model)
- `apps.content` - Resources, Assets, Licenses, Organizations (main business logic)
- `apps.licensing` - Access requests, permissions, usage tracking
- `apps.analytics` - Usage events and statistics
- `apps.search` - MeiliSearch integration and indexing
- `apps.api` - API endpoints and versioning
- `apps.medialib` - File uploads and media management
- `apps.api_keys` - API key authentication and rate limiting

**Supporting:**
- `apps.core` - Base models, utilities, managers
- `mock_api` - Development/testing mock endpoints

### Key Models & Data Flow

```
Publisher Organization → Resource → ResourceVersion → Assets → AssetVersion
                                ↓
User → AssetAccessRequest → AssetAccess → UsageEvent
  ↓
Role (Admin/Publisher/Developer/Reviewer)
```

**Critical Models:**
- `User` (custom) - Extends AbstractUser with Auth0 integration
- `PublishingOrganization` - Content publishers (e.g., Tafsir Center)
- `Resource` - Original content packages (e.g., Tafsir Ibn Katheer CSV)  
- `Asset` - Individual downloadable items extracted from resources
- `License` - Content licensing terms (CC0, CC-BY, etc.)
- `AssetAccessRequest` - Developer access approval workflow
- `UsageEvent` - Analytics tracking for downloads/API calls

### Request Lifecycle

1. **Authentication**: Auth0 → Django JWT validation
2. **Authorization**: Role-based permissions check  
3. **API Routing**: `/api/v1/` → DRF views
4. **Business Logic**: Model managers + custom methods
5. **Response**: JSON via DRF serializers
6. **Analytics**: Async usage event logging via Celery

### File Storage Architecture

- **Development**: MinIO S3-compatible storage
- **Production**: Alibaba Cloud OSS
- **Upload Paths**: Dynamic upload paths via `apps.core.utils`
- **File Types**: Images (thumbnails, avatars) + Documents (PDFs, CSVs, etc.)

## Environment Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose (recommended)

### Local Development Setup

1. **Clone and Environment**
```bash
git clone <repository-url>
cd cms-backend
cp env.example .env
# Edit .env with your local configuration
```

2. **Database Setup (Docker)**
```bash
docker-compose up -d postgres redis
# Wait for services to be ready
```

3. **Python Environment** 
```bash
cd src
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

4. **Django Setup**
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

### Environment Variables

**Essential `.env` variables:**
```bash
# Database
DB_NAME=itqan_cms
DB_USER=itqan_user
DB_PASSWORD=itqan_password
DB_HOST=localhost
DB_PORT=5432

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Storage (MinIO)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# Search
MEILISEARCH_URL=http://localhost:7700
MEILISEARCH_MASTER_KEY=masterKey

# Cache & Queue
REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/0
```

### API Documentation Access
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **OpenAPI JSON**: http://localhost:8000/swagger.json

## Development Workflow

### Git Branch Strategy (ENFORCED)
- `main` - Production (PROTECTED: merge from staging only)  
- `staging` - Pre-production (PROTECTED: merge from develop only)
- `develop` - Active development (direct commits allowed)
- `feature/*` - Feature branches (merge to develop)

**⚠️ CRITICAL**: Direct commits to `main` and `staging` are blocked. Always work on `develop` or feature branches.

### Development Process
```bash
# Start work
git checkout develop
git pull origin develop

# Make changes and test locally  
./dev.sh  # MANDATORY: Test locally before pushing
# Verify at http://local.cms.itqaan.dev:8000 (add to /etc/hosts)

# Commit and push
git add .
git commit -m "Descriptive commit message"
git push origin develop

# Deploy to staging (via PR)
gh pr create --base staging --head develop --title "Promote to staging"
```

### Code Conventions

**Django Patterns:**
- Models use `BaseModel` with soft deletes (`is_active` field)
- UUID primary keys for all custom models
- Managers: `objects` (active only), `all_objects` (including inactive)
- i18n support via `modeltranslation` (English/Arabic)
- API versioning: `/api/v1/` pattern

**Database Design:**
- snake_case for table/column names
- Never drop columns (mark deprecated instead)
- Use database constraints and indexes appropriately
- Foreign keys use `PROTECT` or `CASCADE` based on business rules

**Testing Guidelines:**
- Write tests for all API endpoints
- Test both Publisher and Consumer workflows
- Mock external services (Auth0, MeiliSearch, etc.)
- Use factory patterns for test data generation

### Deployment Pipeline

**Environment URLs:**
- Local: `http://local.cms.itqaan.dev:8000` 
- Develop: `https://dev.cms.itqaan.dev`
- Staging: `https://staging.cms.itqaan.dev`
- Production: `https://cms.itqaan.dev`

**Deployment Commands:**
```bash
# Deploy to development server
./deployment/deploy-develop.sh

# Manual deployment
ssh root@<server-ip>
cd /srv/cms-backend
git pull origin develop
docker-compose up -d --build
```

## Important Project-Specific Details

### Authentication Architecture
The system uses a **hybrid authentication approach**:
- **Frontend**: Auth0 SPA SDK (Angular)
- **Backend**: Custom User model with django-allauth for OAuth only
- **API**: JWT tokens for stateless API authentication
- **Email verification**: Managed in custom User model (not allauth tables)

### Content Licensing Workflow
1. **Publishers** upload Resources with default licenses (V1: CC0 auto-granted)
2. **Developers** browse Asset Store and request access
3. **Access Requests** are auto-approved in V1 (manual review in V2)
4. **AssetAccess** grants download URLs and tracks usage
5. **UsageEvents** log all interactions for analytics

### File Processing Pipeline
- Resources contain raw uploaded files
- Assets are extracted/processed from ResourceVersions  
- Each Asset can have multiple AssetVersions
- File storage uses S3-compatible backends (MinIO/OSS)
- Thumbnails and previews generated on upload

### Cursor Rules Integration
The project includes comprehensive Cursor AI rules in `.cursor/rules/`:
- `cms-v1.mdc` - Full project context and development protocols
- `docs.mdc` - Documentation generation templates
- `screens-flow.mdc` - UI/UX flow documentation

### Key Gotchas

⚠️ **Migration Policy**: Never drop columns - mark as deprecated and remove in future major versions

⚠️ **User Model**: Custom User model extends AbstractUser but integrates with django-allauth for OAuth only (GitHub/Google)

⚠️ **Soft Deletes**: All models use `is_active=False` instead of actual deletion via `BaseModel`

⚠️ **API Versioning**: Always use `/api/v1/` prefix, implement new versions for breaking changes

⚠️ **MeiliSearch**: Async indexing via Celery signals - check search works after model changes

⚠️ **Static Files**: Development uses local storage, production uses CDN - test both paths

## Useful References

- **API Documentation**: `/swagger/` and `/redoc/`
- **Admin Interface**: `/django-admin/` (superuser required)  
- **Wagtail CMS**: `/cms/` (for content management)
- **OpenAPI Spec**: `/openapi.yaml`
- **Health Check**: `/health/`

### External Dependencies
- **Auth0**: User authentication service
- **MeiliSearch**: Full-text search engine
- **MinIO/Alibaba OSS**: Object storage
- **PostgreSQL**: Primary database
- **Redis**: Cache and message broker

### Documentation Links
- Django 4.2 LTS: https://docs.djangoproject.com/en/4.2/
- DRF: https://www.django-rest-framework.org/
- Wagtail: https://docs.wagtail.org/
- Celery: https://docs.celeryproject.org/

---

**🚨 Always test locally before pushing to any branch. The local test requirement is strictly enforced.**
