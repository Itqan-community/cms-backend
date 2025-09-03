# CMS Backend Deployment Guide

## Quick Deploy to Development Server

### Option 1: Automated Script
```bash
# From project root
./deployment/deploy-develop.sh
```

### Option 2: Manual Deployment
```bash
# SSH into development server
ssh root@167.172.227.184

# Navigate to app directory
cd /srv/cms-backend

# Pull latest changes
git pull origin develop

# Update environment
cd deployment/docker
cp env.template .env
nano .env  # Configure with production values

# Restart application
docker compose down
docker compose up -d --build

# Check status
docker compose ps
docker compose logs web
curl http://localhost:8000/health
```

## Environment Configuration

For `develop.api.cms.itqan.dev`, use these settings in `.env`:

```bash
# Core
DEBUG=False
SECRET_KEY=your-production-secret-key
ALLOWED_HOSTS=develop.api.cms.itqan.dev
SITE_DOMAIN=develop.api.cms.itqan.dev

# Database (DigitalOcean)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=defaultdb
DB_USER=doadmin
DB_PASSWORD=AVNS_LpYdVcaUreg2fWj-UTY
DB_HOST=cms-develop-db-do-user-24395859-0.j.db.ondigitalocean.com
DB_PORT=25060
PGSSLMODE=require

# OAuth (optional)
GITHUB_CLIENT_ID=Ov23lizjfvLj3yehPx8M
GITHUB_CLIENT_SECRET=e396cee9a3687f3e4ff72fc5c6f0f084fe62477d

# CORS
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
```

## Testing Deployment

After deployment, test these endpoints:

```bash
# Health check
curl https://develop.api.cms.itqan.dev/health

# API documentation
curl https://develop.api.cms.itqan.dev/api/v1/docs/

# Authentication endpoints
curl -X POST https://develop.api.cms.itqan.dev/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123!"}'
```

## Troubleshooting

### 502 Error
- Check container status: `docker compose ps`
- Check logs: `docker compose logs web`
- Verify `.env` configuration
- Ensure database connectivity

### Database Issues
- Check PostgreSQL connection
- Verify firewall rules allow connection from droplet
- Test connection: `psql "postgresql://user:pass@host:port/db?sslmode=require"`

### Container Issues
- Rebuild: `docker compose up -d --build --force-recreate`
- Check resources: `docker system df`
- Clean up: `docker system prune`
