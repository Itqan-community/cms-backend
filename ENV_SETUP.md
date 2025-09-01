# Environment Configuration Guide

This document describes all environment files and their usage in the Itqan CMS project.

## Environment Files Overview

### Backend Environment Files

#### 1. `backend/.env` (Development - Active)
Current development environment configuration using SQLite.
```bash
# Copy and customize for local development
cp backend/.env.example backend/.env
```

#### 2. `backend/.env.production` (Production Template)
Production-ready configuration with PostgreSQL and security settings.
**⚠️ SECURITY WARNING**: Update all placeholder values before deployment.

Key production settings:
- PostgreSQL database configuration
- Strong secret keys and passwords
- SSL/HTTPS security headers
- Email configuration for notifications
- AWS S3 for static/media files
- Redis for caching

#### 3. `backend/.env.example` (Template)
Template file showing all available environment variables with examples.

### Frontend Environment Files

#### 1. `frontend/.env.local` (Development - Active)
Current development environment for Next.js.
```bash
# Copy and customize for local development
cp frontend/.env.example frontend/.env.local
```

#### 2. `frontend/.env.production` (Production Template)
Production configuration with CDN, analytics, and monitoring.

#### 3. `frontend/.env.example` (Template)
Template showing all available frontend environment variables.

## Quick Setup

### Development Setup
```bash
# Backend
cd backend
cp .env.example .env
# Edit .env with your values

# Frontend
cd ../frontend
cp .env.example .env.local
# Edit .env.local with your values
```

### Production Setup
```bash
# Backend
cd backend
cp .env.production .env
# ⚠️ IMPORTANT: Update all CHANGE_ME values

# Frontend
cd ../frontend
cp .env.production .env.production.local
# Update with your production values
```

## Environment Variables Reference

### Backend Variables

#### Database
- `DB_ENGINE`: Database backend (sqlite3/postgresql)
- `DB_NAME`: Database name
- `DB_USER`: Database username
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host
- `DB_PORT`: Database port

#### Django
- `DEBUG`: Debug mode (True/False)
- `SECRET_KEY`: Django secret key
- `ALLOWED_HOSTS`: Comma-separated allowed hosts

#### Auth0
- `AUTH0_DOMAIN`: Auth0 domain
- `AUTH0_CLIENT_ID`: Auth0 client ID
- `AUTH0_CLIENT_SECRET`: Auth0 client secret
- `AUTH0_AUDIENCE`: Auth0 API audience

#### Security (Production)
- `SECURE_SSL_REDIRECT`: Force HTTPS
- `SECURE_HSTS_SECONDS`: HSTS max age
- `SESSION_COOKIE_SECURE`: Secure session cookies
- `CSRF_COOKIE_SECURE`: Secure CSRF cookies

### Frontend Variables

#### Core
- `NEXT_PUBLIC_BACKEND_URL`: Backend API URL
- `NEXT_PUBLIC_APP_URL`: Frontend app URL
- `NODE_ENV`: Environment (development/production)

#### Auth0
- `NEXT_PUBLIC_AUTH0_DOMAIN`: Auth0 domain
- `NEXT_PUBLIC_AUTH0_CLIENT_ID`: Auth0 client ID
- `NEXT_PUBLIC_AUTH0_AUDIENCE`: Auth0 API audience

#### Analytics & Monitoring
- `NEXT_PUBLIC_GA_MEASUREMENT_ID`: Google Analytics ID
- `NEXT_PUBLIC_HOTJAR_ID`: Hotjar tracking ID
- `NEXT_PUBLIC_SENTRY_DSN`: Sentry error tracking

## Security Best Practices

### 🔒 Production Security Checklist

1. **Never commit `.env` files to version control**
2. **Use strong, unique passwords and secret keys**
3. **Enable HTTPS in production**
4. **Set DEBUG=False in production**
5. **Use environment-specific Auth0 applications**
6. **Configure proper CORS settings**
7. **Set up proper database backups**
8. **Use secure session and CSRF cookies**

### 🔑 Secret Generation

Generate secure secrets:
```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Strong password
openssl rand -base64 32
```

## Deployment Notes

### Database Migration
When switching from SQLite to PostgreSQL:
1. Update `DB_ENGINE` to `django.db.backends.postgresql`
2. Set PostgreSQL connection details
3. Run migrations: `python manage.py migrate`

### Docker Setup
PostgreSQL and Redis are configured via `docker-compose.yml`:
```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps
```

## Troubleshooting

### Common Issues

1. **Database connection errors**: Check DB credentials and host
2. **Auth0 errors**: Verify domain, client ID, and audience
3. **CORS errors**: Check `ALLOWED_HOSTS` and CORS settings
4. **Static files not loading**: Verify `STATIC_URL` and `STATIC_ROOT`

### Environment Validation
```bash
# Backend
cd backend
python manage.py check

# Frontend
cd frontend
npm run build
```
