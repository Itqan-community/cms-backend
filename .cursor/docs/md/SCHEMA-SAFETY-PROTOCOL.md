# Schema Safety Protocol - Preventing Database Mismatches

**Date:** 2025-09-08  
**Author:** AI Assistant  

## Overview
This document establishes mandatory protocols to prevent database schema mismatches like the Asset-Resource relationship issue we encountered. These tools and procedures ensure database schema always matches Django model definitions.

## Problem We Solved
- **Issue**: Database had `publishing_organization_id` but Django models expected `resource_id`
- **Cause**: "Fresh" migrations applied to databases with old schema
- **Impact**: `ProgrammingError: column asset.resource_id does not exist`
- **Root Cause**: No verification that database schema matched model definitions

## Prevention Tools Implemented

### 1. Schema Verification Command
**File**: `apps/core/management/commands/verify_schema.py`

**Usage**:
```bash
# Check schema matches models
python manage.py verify_schema

# Check specific app
python manage.py verify_schema --app content

# Auto-create migrations for mismatches
python manage.py verify_schema --fix
```

**Features**:
- ✅ Compares database tables with Django model definitions
- ✅ Identifies missing columns, extra columns, type mismatches
- ✅ Can automatically create migrations to fix issues
- ✅ Validates critical relationships (Asset-Resource)

### 2. Safe Migration Script
**File**: `deployment/scripts/safe_migration.sh`

**Usage**:
```bash
# Safe migration for development
./deployment/scripts/safe_migration.sh development

# Safe migration for staging  
./deployment/scripts/safe_migration.sh staging

# Safe migration for production
./deployment/scripts/safe_migration.sh production
```

**Process**:
1. ✅ Pre-migration schema verification
2. ✅ Schema backup creation
3. ✅ Migration plan display
4. ✅ User confirmation
5. ✅ Migration execution
6. ✅ Post-migration verification
7. ✅ System checks

### 3. Pre-Deployment Checks
**File**: `deployment/pre-deploy-checks.sh`

**Usage**:
```bash
# Check before deployment
./deployment/pre-deploy-checks.sh development
./deployment/pre-deploy-checks.sh staging
./deployment/pre-deploy-checks.sh production
```

**Verifies**:
- ✅ Git repository status
- ✅ Correct branch for environment
- ✅ Environment connectivity
- ✅ Docker container status
- ✅ Database schema consistency
- ✅ Migration status
- ✅ Critical model relationships
- ✅ Admin user existence

### 4. GitHub Actions CI/CD
**File**: `.github/workflows/schema-verification.yml`

**Triggers**:
- Pull requests touching models or migrations
- Pushes to main/develop/staging branches

**Checks**:
- ✅ Schema consistency in test database
- ✅ Missing migrations detection
- ✅ Critical model verification (Asset-Resource)
- ✅ Migration conflict detection

## Mandatory Procedures

### Before Any Migration
```bash
# 1. Verify current schema
python manage.py verify_schema

# 2. Use safe migration script
./deployment/scripts/safe_migration.sh [environment]
```

### Before Any Deployment
```bash
# 1. Run pre-deployment checks
./deployment/pre-deploy-checks.sh [environment]

# 2. Only proceed if all checks pass
```

### Emergency Override
If you must skip verification (emergencies only):
```bash
# Skip verification (use carefully!)
SKIP_VERIFICATION=true ./deployment/pre-deploy-checks.sh [environment]
```

## Critical Checkpoints

### Asset-Resource Relationship
The tools specifically verify:
- ✅ `asset` table has `resource_id` column (not `publishing_organization_id`)
- ✅ Asset model properly connects to Resource model
- ✅ Admin interface updated for new relationship

### Database Schema Consistency
All environments must have:
- ✅ Identical schema structure
- ✅ Same column names and types
- ✅ Consistent foreign key relationships

## Integration with Development Workflow

### Updated CMS Rules
Added to `.cursor/rules/cms-v1.mdc`:
- **Schema Safety Protocol**: Mandatory verification before deployment/migration
- **Deployment Safety**: Always run pre-deployment checks
- **Migration Safety**: Use safe migration scripts

### Developer Workflow
1. **Make model changes**
2. **Run**: `python manage.py verify_schema --fix`
3. **Create migrations**: `python manage.py makemigrations`
4. **Test locally**: `./deployment/scripts/safe_migration.sh development`
5. **Deploy**: `./deployment/pre-deploy-checks.sh [environment]`

## Monitoring and Alerts

### CI/CD Integration
- ✅ GitHub Actions run schema verification on every PR
- ✅ Deployment blocked if schema verification fails
- ✅ Automatic detection of migration conflicts

### Manual Checks
Run these commands regularly:
```bash
# Daily schema health check
python manage.py verify_schema

# Before major deployments
./deployment/pre-deploy-checks.sh production
```

## Recovery Procedures

### If Schema Mismatch Detected
1. **Stop**: Do not proceed with deployment
2. **Investigate**: Run `python manage.py verify_schema` for details
3. **Fix**: Either create migrations or fix model definitions
4. **Verify**: Ensure verification passes before continuing

### If Deployment Fails Due to Schema
1. **Rollback**: Use backup or previous Git commit
2. **Fix Schema**: Apply correct migrations
3. **Test**: Verify in staging environment first
4. **Re-deploy**: Only after verification passes

## Success Metrics

### Prevented Issues
- ✅ Zero `column does not exist` errors
- ✅ Consistent schema across all environments
- ✅ Successful migrations without manual intervention
- ✅ Reduced deployment failures

### Quality Gates
- ✅ All deployments pass pre-deployment checks
- ✅ All migrations use safe migration script
- ✅ CI/CD catches schema issues before merge

## Next Steps

1. **Train team** on new procedures
2. **Integrate** into deployment pipelines
3. **Monitor** schema consistency across environments
4. **Improve** tools based on usage feedback

## References
- Schema Verification Command: `apps/core/management/commands/verify_schema.py`
- Safe Migration Script: `deployment/scripts/safe_migration.sh`
- Pre-deployment Checks: `deployment/pre-deploy-checks.sh`
- GitHub Actions: `.github/workflows/schema-verification.yml`
- Updated CMS Rules: `.cursor/rules/cms-v1.mdc`
