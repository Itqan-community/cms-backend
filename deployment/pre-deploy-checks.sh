#!/bin/bash
set -e

# Pre-deployment Schema Safety Checks
# Run this before any deployment to prevent schema mismatches

echo "🛡️  PRE-DEPLOYMENT SAFETY CHECKS"
echo "================================="

ENVIRONMENT=${1:-"development"}
SKIP_VERIFICATION=${SKIP_VERIFICATION:-false}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "src/manage.py" ]; then
    log_error "Must be run from project root directory"
    exit 1
fi

# Determine docker compose file
case $ENVIRONMENT in
    "development"|"develop")
        COMPOSE_FILE="deployment/docker/docker-compose.develop.yml"
        DOMAIN="develop.api.cms.itqan.dev"
        ;;
    "staging")
        COMPOSE_FILE="deployment/docker/docker-compose.staging.yml"
        DOMAIN="staging.api.cms.itqan.dev"
        ;;
    "production"|"prod")
        COMPOSE_FILE="deployment/docker/docker-compose.production.yml"
        DOMAIN="api.cms.itqan.dev"
        ;;
    *)
        log_error "Unknown environment: $ENVIRONMENT"
        log_info "Valid environments: development, staging, production"
        exit 1
        ;;
esac

log_info "Environment: $ENVIRONMENT"
log_info "Domain: $DOMAIN"
log_info "Compose file: $COMPOSE_FILE"

# Function to run docker command
run_docker_cmd() {
    docker compose -f "$COMPOSE_FILE" exec web "$@"
}

# Check 1: Git status
echo ""
log_info "Check 1: Git Repository Status"
if [ -n "$(git status --porcelain)" ]; then
    log_warning "Working directory has uncommitted changes"
    git status --short
    echo ""
    read -p "Continue with uncommitted changes? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Deployment cancelled"
        exit 1
    fi
else
    log_success "Working directory clean"
fi

# Check 2: Branch verification
echo ""
log_info "Check 2: Branch Verification"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "Current branch: $CURRENT_BRANCH"

case $ENVIRONMENT in
    "production")
        if [ "$CURRENT_BRANCH" != "main" ]; then
            log_warning "Production deployments should be from 'main' branch"
            read -p "Continue from '$CURRENT_BRANCH' branch? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_error "Deployment cancelled"
                exit 1
            fi
        fi
        ;;
    "staging")
        if [ "$CURRENT_BRANCH" != "staging" ] && [ "$CURRENT_BRANCH" != "main" ]; then
            log_warning "Staging deployments should be from 'staging' or 'main' branch"
        fi
        ;;
    "development")
        if [ "$CURRENT_BRANCH" != "develop" ] && [ "$CURRENT_BRANCH" != "main" ]; then
            log_warning "Development deployments should be from 'develop' or 'main' branch"
        fi
        ;;
esac

# Check 3: Environment connectivity
echo ""
log_info "Check 3: Environment Connectivity"
if curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/django-admin/" | grep -q "302"; then
    log_success "Environment is reachable and responding"
else
    log_error "Environment is not responding correctly"
    log_info "URL: https://$DOMAIN/django-admin/"
    exit 1
fi

# Check 4: Docker containers status
echo ""
log_info "Check 4: Docker Containers Status"
if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
    log_success "Docker containers are running"
    docker compose -f "$COMPOSE_FILE" ps
else
    log_error "Docker containers are not running"
    log_info "Start containers first: docker compose -f $COMPOSE_FILE up -d"
    exit 1
fi

# Check 5: Database schema verification
if [ "$SKIP_VERIFICATION" != "true" ]; then
    echo ""
    log_info "Check 5: Database Schema Verification"
    
    if run_docker_cmd python manage.py verify_schema > /dev/null 2>&1; then
        log_success "Database schema matches model definitions"
    else
        log_error "Database schema verification failed!"
        log_warning "Schema mismatch detected. This is exactly what we're trying to prevent!"
        echo ""
        log_info "Running detailed verification..."
        run_docker_cmd python manage.py verify_schema
        echo ""
        log_error "🛑 DEPLOYMENT BLOCKED - Schema mismatch detected"
        log_info "💡 Fix options:"
        log_info "   1. Run: python manage.py verify_schema --fix"
        log_info "   2. Create proper migrations: python manage.py makemigrations"
        log_info "   3. Use safe migration script: ./deployment/scripts/safe_migration.sh"
        log_info "   4. Skip verification: SKIP_VERIFICATION=true ./deployment/pre-deploy-checks.sh"
        exit 1
    fi
fi

# Check 6: Migration status
echo ""
log_info "Check 6: Migration Status"
PENDING_COUNT=$(run_docker_cmd python manage.py showmigrations --plan | grep "\[ \]" | wc -l || echo "0")

if [ "$PENDING_COUNT" -gt 0 ]; then
    log_warning "Found $PENDING_COUNT pending migration(s)"
    run_docker_cmd python manage.py showmigrations --plan | grep "\[ \]"
    echo ""
    log_info "💡 Recommendation: Use safe migration script"
    log_info "   ./deployment/scripts/safe_migration.sh $ENVIRONMENT"
else
    log_success "No pending migrations"
fi

# Check 7: Critical model verification
echo ""
log_info "Check 7: Critical Model Verification (Asset-Resource relationship)"
ASSET_CHECK=$(run_docker_cmd python manage.py shell -c "
from django.db import connection
cursor = connection.cursor()
cursor.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name = 'asset' AND column_name = 'resource_id'\")
result = cursor.fetchone()
print('OK' if result else 'MISSING')
" 2>/dev/null | tail -1)

if [ "$ASSET_CHECK" = "OK" ]; then
    log_success "Asset-Resource relationship verified (resource_id column exists)"
else
    log_error "CRITICAL: Asset table missing resource_id column!"
    log_error "This indicates the Asset-Resource relationship fix was not applied properly"
    exit 1
fi

# Check 8: Admin user verification
echo ""
log_info "Check 8: Admin User Verification"
ADMIN_EMAIL=""
case $ENVIRONMENT in
    "development")
        ADMIN_EMAIL="admin@develop.cms.itqan.dev"
        ;;
    "staging")
        ADMIN_EMAIL="admin@staging.cms.itqan.dev"
        ;;
    "production")
        ADMIN_EMAIL="admin@itqan.dev"
        ;;
esac

ADMIN_EXISTS=$(run_docker_cmd python manage.py shell -c "
from apps.accounts.models import User
user = User.objects.filter(email='$ADMIN_EMAIL').first()
print('OK' if user and user.is_superuser else 'MISSING')
" 2>/dev/null | tail -1)

if [ "$ADMIN_EXISTS" = "OK" ]; then
    log_success "Admin user verified: $ADMIN_EMAIL"
else
    log_warning "Admin user missing or not superuser: $ADMIN_EMAIL"
    log_info "💡 Create admin user: python manage.py ensure_superuser --email='$ADMIN_EMAIL' --username='admin' --password='ItqanCMS2024!'"
fi

# Final summary
echo ""
echo "🎯 PRE-DEPLOYMENT CHECKS SUMMARY"
echo "================================="
log_success "Environment: $ENVIRONMENT"
log_success "Domain: $DOMAIN"
log_success "Git status: $([ -z "$(git status --porcelain)" ] && echo "Clean" || echo "Has changes")"
log_success "Containers: Running"
log_success "Database schema: Valid"
log_success "Migrations: $PENDING_COUNT pending"
log_success "Asset-Resource relationship: Valid"
log_success "Admin user: $ADMIN_EXISTS"

echo ""
if [ "$PENDING_COUNT" -gt 0 ]; then
    log_warning "⚠️  $PENDING_COUNT pending migrations - run safe migration script"
    log_info "Next: ./deployment/scripts/safe_migration.sh $ENVIRONMENT"
else
    log_success "🚀 Ready for deployment!"
fi

echo ""
log_info "Admin login: https://$DOMAIN/django-admin/"
log_info "Email: $ADMIN_EMAIL"
log_info "Password: ItqanCMS2024!"
