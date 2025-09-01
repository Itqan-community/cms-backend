# Docker Deployment for Itqan CMS Backend

This directory contains Docker configuration files for deploying the Itqan CMS backend to DigitalOcean.

## Architecture

- **Web Service**: Django application with Gunicorn
- **Reverse Proxy**: Caddy for automatic HTTPS and static file serving
- **Database**: DigitalOcean Managed PostgreSQL
- **Storage**: Docker volumes for static files and media

## Environment Setup

### 1. DigitalOcean Resources Required

For each environment (develop, staging, production):
- 1x Droplet (Ubuntu 22.04, 1-2GB RAM)
- 1x Managed PostgreSQL database
- DNS A records pointing to droplet IPs

### 2. Environment Variables

Copy `env.template` to `.env` on each droplet and configure:

```bash
# Copy template
cp deployment/docker/env.template deployment/docker/.env

# Edit with your values
nano deployment/docker/.env
```

**Required variables:**
- `SECRET_KEY`: Unique Django secret key per environment
- `ALLOWED_HOSTS`: Your domain (e.g., staging.api.cms.itqan.dev)
- `SITE_DOMAIN`: Same as ALLOWED_HOSTS
- `DB_*`: Database connection details from DigitalOcean
- `AUTH0_*`: Auth0 configuration

### 3. Deployment Commands

**Initial deployment:**
```bash
# Clone repository
git clone https://github.com/Itqan-community/cms-backend.git /srv/cms-backend
cd /srv/cms-backend
git checkout <branch>

# Create environment file
cp deployment/docker/env.template deployment/docker/.env
nano deployment/docker/.env  # Configure your values

# Start services
docker compose -f deployment/docker/docker-compose.yml up -d --build
```

**Update deployment:**
```bash
cd /srv/cms-backend
git pull origin <branch>
docker compose -f deployment/docker/docker-compose.yml up -d --build
```

## Domain Configuration

The Caddyfile automatically handles:
- HTTPS certificate provisioning via Let's Encrypt
- HTTP to HTTPS redirect
- Static file serving
- Reverse proxy to Django application

Ensure your DNS A records point to the correct droplet IPs:
- `develop.api.cms.itqan.dev` → develop droplet IP
- `staging.api.cms.itqan.dev` → staging droplet IP  
- `api.cms.itqan.dev` → production droplet IP

## Monitoring and Logs

**View application logs:**
```bash
docker compose -f deployment/docker/docker-compose.yml logs -f web
```

**View Caddy logs:**
```bash
docker compose -f deployment/docker/docker-compose.yml logs -f caddy
```

**Health check:**
```bash
curl https://your-domain.com/health
```

## Troubleshooting

**Common issues:**

1. **Database connection failed**
   - Verify DigitalOcean managed database allows connections from your droplet
   - Check `DB_*` environment variables
   - Ensure SSL mode is set correctly (`PGSSLMODE=require`)

2. **SSL certificate issues**
   - Verify DNS records point to correct droplet
   - Check Caddy logs: `docker compose logs caddy`
   - Ensure ports 80 and 443 are open in firewall

3. **Static files not loading**
   - Run `docker compose exec web python manage.py collectstatic`
   - Check static file volume mounts

4. **Application not starting**
   - Check web service logs: `docker compose logs web`
   - Verify all required environment variables are set
   - Check database connectivity

## Security Notes

- Never commit `.env` files to version control
- Use strong, unique `SECRET_KEY` values per environment
- Regularly update Docker images and dependencies
- Monitor application logs for security issues
- Use DigitalOcean managed database for automatic backups and security updates
