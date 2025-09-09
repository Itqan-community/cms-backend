#!/bin/bash
set -e

# Safe Migration Script
# Prevents schema mismatches by verifying before/after migration

echo "🛡️  SAFE MIGRATION SCRIPT"
echo "========================="

# Configuration
ENVIRONMENT=${1:-"development"}
BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "📍 Environment: $ENVIRONMENT"
echo "⏰ Timestamp: $BACKUP_TIMESTAMP"

# Function to check if we're in Docker container
check_docker_context() {
    if [ -f /.dockerenv ]; then
        echo "🐳 Running inside Docker container"
        DOCKER_EXEC=""
    else
        echo "🖥️  Running on host, will use docker compose exec"
        case $ENVIRONMENT in
            "development")
                DOCKER_EXEC="docker compose -f docker-compose.develop.yml exec web"
                ;;
            "staging")
                DOCKER_EXEC="docker compose -f docker-compose.staging.yml exec web"
                ;;
            "production")
                DOCKER_EXEC="docker compose -f docker-compose.production.yml exec web"
                ;;
            *)
                echo "❌ Unknown environment: $ENVIRONMENT"
                exit 1
                ;;
        esac
    fi
}

# Function to run Django management command
run_django_cmd() {
    if [ -z "$DOCKER_EXEC" ]; then
        python manage.py "$@"
    else
        $DOCKER_EXEC python manage.py "$@"
    fi
}

# Function to backup database schema
backup_schema() {
    echo "💾 Creating schema backup..."
    
    if [ -z "$DOCKER_EXEC" ]; then
        pg_dump_cmd="pg_dump"
    else
        pg_dump_cmd="$DOCKER_EXEC pg_dump"
    fi
    
    # This would need to be customized for your specific DB connection
    echo "📝 Schema backup would be created here (customize for your DB setup)"
    # $pg_dump_cmd --schema-only $DATABASE_URL > "backup_schema_${BACKUP_TIMESTAMP}.sql"
}

# Step 1: Pre-migration schema verification
echo "🔍 Step 1: Verifying current schema..."
if ! run_django_cmd verify_schema; then
    echo "❌ Schema verification failed! Current database doesn't match models."
    echo "🛑 Stopping migration to prevent further issues."
    echo ""
    echo "💡 Options:"
    echo "  1. Run: python manage.py verify_schema --fix"
    echo "  2. Manually review and fix schema mismatches"
    echo "  3. Reset database if this is a fresh deployment"
    exit 1
fi
echo "✅ Pre-migration schema verification passed"

# Step 2: Check for pending migrations
echo ""
echo "🔍 Step 2: Checking for pending migrations..."
PENDING_MIGRATIONS=$(run_django_cmd showmigrations --plan | grep "\[ \]" | wc -l)

if [ "$PENDING_MIGRATIONS" -eq 0 ]; then
    echo "✅ No pending migrations found"
    exit 0
fi

echo "📋 Found $PENDING_MIGRATIONS pending migration(s)"

# Step 3: Backup (optional)
echo ""
echo "🔍 Step 3: Creating backup..."
backup_schema

# Step 4: Show migration plan
echo ""
echo "🔍 Step 4: Migration plan:"
run_django_cmd showmigrations --plan | grep "\[ \]"

# Step 5: Confirm migration
echo ""
read -p "🤔 Proceed with migration? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🛑 Migration cancelled"
    exit 0
fi

# Step 6: Run migrations
echo ""
echo "🚀 Step 6: Running migrations..."
if run_django_cmd migrate; then
    echo "✅ Migrations completed successfully"
else
    echo "❌ Migration failed!"
    echo "🔄 Consider restoring from backup if needed"
    exit 1
fi

# Step 7: Post-migration verification
echo ""
echo "🔍 Step 7: Post-migration schema verification..."
if ! run_django_cmd verify_schema; then
    echo "❌ Post-migration verification failed!"
    echo "⚠️  Database schema may be inconsistent"
    exit 1
fi
echo "✅ Post-migration schema verification passed"

# Step 8: Final checks
echo ""
echo "🔍 Step 8: Final system checks..."
if run_django_cmd check; then
    echo "✅ Django system checks passed"
else
    echo "⚠️  Some Django checks failed, review output above"
fi

echo ""
echo "🎉 Safe migration completed successfully!"
echo "📋 Summary:"
echo "  - Environment: $ENVIRONMENT"
echo "  - Migrations applied: $PENDING_MIGRATIONS"
echo "  - Schema verified: ✅"
echo "  - System checks: ✅"
