# Environment Configuration Guide

This guide explains how to deploy the CMS backend across different environments.

## 🌍 Environment Overview

| Environment | Settings Module | Domain | Docker Compose File |
|-------------|----------------|---------|---------------------|
| **Development** | `config.settings.development` | `develop.api.cms.itqan.dev` | `docker-compose.yml` |
| **Staging** | `config.settings.staging` | `staging.api.cms.itqan.dev` | `docker-compose.staging.yml` |
| **Production** | `config.settings.production` | `api.cms.itqan.dev` | `docker-compose.production.yml` |

## 🚀 Deployment Instructions

### Development Environment

```bash
# Use the default docker-compose.yml (already configured for development)
cd /srv/cms-backend/deployment/docker
cp env.template .env
# Edit .env with development values
docker compose up -d --build
```

### Staging Environment

```bash
# Use staging-specific compose file
cd /srv/cms-backend/deployment/docker
cp env.staging.template .env
# Edit .env with staging values
docker compose -f docker-compose.staging.yml up -d --build
```

### Production Environment

```bash
# Use production-specific compose file
cd /srv/cms-backend/deployment/docker
cp env.template .env
# Edit .env with production values
docker compose -f docker-compose.production.yml up -d --build
```

## ⚙️ Environment-Specific Settings

### Development Settings (`development.py`)
- **DEBUG**: `True`
- **ALLOWED_HOSTS**: `['localhost', '127.0.0.1', '0.0.0.0', 'develop.api.cms.itqan.dev']`
- **Cache**: Dummy cache (no Redis required)
- **Email**: Console backend (logs to console)
- **Security**: Relaxed settings for development
- **CORS**: Allow all origins
- **Logging**: DEBUG level

### Staging Settings (`staging.py`)
- **DEBUG**: `False` (production-like)
- **ALLOWED_HOSTS**: `['staging.api.cms.itqan.dev', 'localhost']`
- **Cache**: Dummy cache (no Redis required)
- **Email**: Console backend or SMTP
- **Security**: Production-like security settings
- **CORS**: Specific allowed origins
- **Logging**: INFO level (more verbose than production)
- **OAuth**: Uses staging/test app credentials

### Production Settings (`production.py`)
- **DEBUG**: `False`
- **ALLOWED_HOSTS**: `['api.itqan.com', 'cms.itqan.com', '.itqan.com', 'api.cms.itqan.dev']`
- **Cache**: Redis cache (when available)
- **Email**: SMTP backend
- **Security**: Full security settings enabled
- **CORS**: Restricted allowed origins
- **Logging**: WARNING level
- **OAuth**: Uses production app credentials

## 🔑 Environment Variables

Each environment requires specific environment variables. Use the appropriate template:

- **Development**: `env.template`
- **Staging**: `env.staging.template`
- **Production**: `env.template` (with production values)

### Key Variables to Configure

```bash
# Required for all environments
DJANGO_SETTINGS_MODULE=config.settings.{environment}
SECRET_KEY=your-secret-key
SITE_DOMAIN=your-domain
DB_NAME=your-db-name
DB_USER=your-db-user
DB_PASSWORD=your-db-password
DB_HOST=your-db-host
DB_PORT=25060

# OAuth credentials (environment-specific)
GOOGLE_OAUTH2_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH2_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

## 🔄 Switching Environments

To switch an existing deployment to a different environment:

1. **Stop current containers**:
   ```bash
   docker compose down
   ```

2. **Update environment variables**:
   ```bash
   # Edit .env file with new environment values
   vim .env
   ```

3. **Use appropriate compose file**:
   ```bash
   # For staging
   docker compose -f docker-compose.staging.yml up -d --build
   
   # For production
   docker compose -f docker-compose.production.yml up -d --build
   ```

## 🗄️ Database Migrations

Each environment should have its own database. When deploying to a new environment:

1. **Reset migrations** (for clean slate):
   ```bash
   docker compose run --rm web python manage.py shell -c "
   from django.db import connection
   cursor = connection.cursor()
   cursor.execute('TRUNCATE TABLE django_migrations;')
   "
   ```

2. **Apply migrations**:
   ```bash
   docker compose run --rm web python manage.py migrate
   ```

## 🔍 Verification

After deployment, verify each environment:

```bash
# Check health endpoint
curl https://{domain}/health/

# Check API docs
curl https://{domain}/api/v1/docs/

# Check auth endpoints
curl -X POST https://{domain}/api/v1/auth/register/ -H "Content-Type: application/json" -d "{}"
```

Expected responses:
- Health: `200 OK`
- API Docs: `200 OK`
- Auth Register: `409 Conflict` (for empty data)

## 📋 Troubleshooting

### Common Issues

1. **ALLOWED_HOSTS error**: Ensure domain is added to appropriate settings file
2. **Redis connection error**: Check if Redis is available or use dummy cache
3. **Database connection error**: Verify DB credentials and SSL settings
4. **Migration conflicts**: Reset migration history and apply fresh migrations

### Logs

Check application logs:
```bash
docker compose logs web --tail=50 -f
```

### Health Checks

Each environment has health checks configured. Monitor with:
```bash
docker compose ps
```
