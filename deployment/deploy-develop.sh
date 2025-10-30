#!/bin/bash
set -e

echo "🚀 Deploying CMS Backend to Development Server"
echo "════════════════════════════════════════════"

# Server details
SERVER_IP="167.172.227.184"
SERVER_USER="root"
APP_DIR="/srv/cms-backend"

echo "📡 Connecting to development server..."

# SSH into server and execute deployment commands
ssh $SERVER_USER@$SERVER_IP << 'EOF'
    set -e

    echo "📁 Navigating to application directory..."
    cd /srv/cms-backend

    echo "🔄 Pulling latest changes..."
    git pull origin develop

    echo "📝 Creating production environment file..."
    cd deployment/docker

    # Create .env file with production settings
    cat > .env << 'ENVEOF'
# Django Configuration
DEBUG=False
SECRET_KEY=django-insecure-change-this-in-production-very-long-random-secret-key-for-cms-backend-develop
ALLOWED_HOSTS=develop.api.cms.itqan.dev,localhost,127.0.0.1
SITE_DOMAIN=develop.api.cms.itqan.dev

# Database Configuration (DigitalOcean Managed PostgreSQL)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=defaultdb
DB_USER=doadmin
DB_PASSWORD=AVNS_LpYdVcaUreg2fWj-UTY
DB_HOST=cms-develop-db-do-user-24395859-0.j.db.ondigitalocean.com
DB_PORT=25060
PGSSLMODE=require

# GitHub OAuth Configuration
GITHUB_CLIENT_ID=Ov23lizjfvLj3yehPx8M
GITHUB_CLIENT_SECRET=e396cee9a3687f3e4ff72fc5c6f0f084fe62477d

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://develop.cms.itqan.dev,https://cms.itqan.dev

# Django Superuser (for initial setup)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@itqan.dev
DJANGO_SUPERUSER_PASSWORD=ItqanCMS2024!

# Docker Image Configuration
IMAGE_REPO=ghcr.io/itqan-community/cms-backend
IMAGE_TAG=develop-$(git rev-parse --short HEAD)
ENVEOF

    echo "✅ Environment file created"

    echo "🔐 Logging in to GitHub Container Registry..."
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin || {
        echo "❌ GHCR login failed, trying with default token...";
        echo "$GITHUB_TOKEN" | docker login ghcr.io -u "itqan-community" --password-stdin || {
            echo "⚠️ GHCR login failed, will try to pull public image";
        }
    }

    echo "🐳 Stopping web container only (preserving caddy)..."
    docker compose -f docker-compose.develop.yml stop web || true
    docker compose -f docker-compose.develop.yml rm -f web || true

    echo "📥 Pulling latest image..."
    docker compose -f docker-compose.develop.yml pull web || echo "⚠️ Pull failed, will use cached image"

    echo "🚀 Starting web container (preserving caddy)..."
    docker compose -f docker-compose.develop.yml up -d web

    echo "⏳ Waiting for application to start..."
    sleep 30

    echo "🔍 Checking application status..."
    docker compose -f docker-compose.develop.yml ps

    echo "📋 Checking application logs..."
    docker compose -f docker-compose.develop.yml logs web --tail=30

    echo "🩺 Waiting for health check to pass..."
    for i in {1..10}; do
        if curl -f http://localhost:8000/health/; then
            echo "✅ Health check passed!"
            break
        else
            echo "⏳ Health check failed, attempt $i/10. Waiting 10 seconds..."
            sleep 10
        fi
    done

    echo ""
    echo "✅ Deployment completed!"
    echo "🌐 API Documentation: https://develop.api.cms.itqan.dev/api/v1/docs/"
    echo "🔧 Check logs with: docker compose logs web"
EOF

echo ""
echo "🎯 Deployment script completed!"
echo "📍 Next steps:"
echo "   1. Test API docs: https://develop.api.cms.itqan.dev/api/v1/docs/"
echo "   2. Test auth endpoints with curl"
echo "   3. Monitor logs: ssh root@$SERVER_IP 'cd /srv/cms-backend/deployment/docker && docker compose -f docker-compose.develop.yml logs web'"
