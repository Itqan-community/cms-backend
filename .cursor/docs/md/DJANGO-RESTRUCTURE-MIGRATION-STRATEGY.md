# Django Restructure - Migration Strategy

## Overview
This document outlines the safe migration strategy for restructuring the Itqan CMS Django project while maintaining zero-downtime deployment and preserving all existing functionality.

## Migration Approach: Incremental & Safe

### Strategy: "Ship of Theseus" Approach
We'll replace components incrementally while keeping the system functional, similar to gradually replacing parts of a ship while it's sailing.

## Phase-by-Phase Migration Plan

### Phase 1: Safety First (Week 1)
**Goal:** Prepare for safe migration without breaking changes

#### 1.1 Create Safety Net
```bash
# Create backup branch
git checkout -b backup/pre-restructure
git push origin backup/pre-restructure

# Create migration branch
git checkout develop
git checkout -b feature/django-restructure
```

#### 1.2 Parallel Structure Setup
- Keep existing structure functional
- Create new structure alongside old one
- Test both work simultaneously

#### 1.3 Add Comprehensive Tests
```bash
# Before any changes, ensure we have baseline tests
python manage.py test
coverage run --source='.' manage.py test
coverage report
```

### Phase 2: Non-Breaking Changes (Week 1-2)
**Goal:** Implement improvements that don't break existing functionality

#### 2.1 Add Missing Files (Safe)
- Create missing `urls.py` files in apps
- Add environment-specific settings
- Create shared libraries structure
- All additive changes only

#### 2.2 URL Configuration Enhancement
```python
# config/urls.py - Gradual transition
urlpatterns = [
    # Existing patterns (keep working)
    path('api/v1/', include('apps.api.urls')),
    path('api/v1/auth/', include('apps.accounts.urls')),
    
    # New organized patterns (add alongside)
    path('api/v1/content/', include('apps.content.urls')),  # NEW
    path('api/v1/licensing/', include('apps.licensing.urls')),  # NEW
    
    # Keep existing catch-all patterns
    path('', include('apps.medialib.urls')),
    path('', include(wagtail_urls)),
]
```

### Phase 3: Directory Cleanup (Week 2)
**Goal:** Remove duplicates safely

#### 3.1 Analyze Before Removing
```bash
# Verify no unique code in duplicate directories
find core/ -name "*.py" -exec grep -l "class\|def\|import" {} \;
find itqan_cms/ -name "*.py" -exec grep -l "class\|def\|import" {} \;

# Check for any imports
grep -r "from core\." / --exclude-dir=apps
grep -r "from itqan_cms" /
```

#### 3.2 Safe Removal Process
```bash
# Move rather than delete initially
mv core/ core.backup/
mv itqan_cms/ itqan_cms.backup/

# Test everything still works
python manage.py test
python manage.py runserver

# If tests pass, commit the move
git add -A
git commit -m "Safe removal of duplicate directories"
```

### Phase 4: Environment Testing (Week 2-3)
**Goal:** Ensure all environments work correctly

#### 4.1 Local Environment Testing
```bash
# Test each environment setting
DJANGO_ENV=development python manage.py runserver
DJANGO_ENV=testing python manage.py test
DJANGO_ENV=staging python manage.py check
```

#### 4.2 Docker Environment Testing
```bash
# Test Docker build with new structure
docker compose -f deployment/docker/docker-compose.yml build
docker compose -f deployment/docker/docker-compose.yml up -d
```

#### 4.3 Deployment Pipeline Testing
- Test GitHub Actions with restructured code
- Verify migrations still work
- Confirm health checks pass

### Phase 5: Production Migration (Week 3)
**Goal:** Deploy to production safely

#### 5.1 Staging Deployment First
```bash
# Deploy to staging environment
git checkout staging
git merge feature/django-restructure
git push origin staging

# Monitor staging for 24-48 hours
# Check logs, performance, functionality
```

#### 5.2 Production Deployment
```bash
# Only after staging validation
git checkout main
git merge staging
git push origin main

# Monitor deployment closely
# Have rollback plan ready
```

## Risk Mitigation Strategies

### Import Path Management
```python
# config/settings/base.py
# Add backward compatibility imports if needed
import sys
import os

# Add old paths to Python path temporarily
old_paths = [
    os.path.join(BASE_DIR, 'legacy_modules'),
]
for path in old_paths:
    if path not in sys.path and os.path.exists(path):
        sys.path.append(path)
```

### Database Safety
- No database schema changes during restructure
- Keep all migrations working
- Test migration rollback capability

### URL Compatibility
```python
# Maintain backward compatibility for critical URLs
urlpatterns = [
    # New clean URLs
    path('api/v1/content/', include('apps.content.urls')),
    
    # Legacy URL redirects (temporary)
    path('old-path/', RedirectView.as_view(url='/api/v1/content/')),
]
```

## Rollback Procedures

### Immediate Rollback (< 1 hour)
```bash
# Quick rollback to previous deployment
git checkout backup/pre-restructure
git push origin develop --force

# Trigger redeployment
# Monitor recovery
```

### Partial Rollback (Selective)
```bash
# Rollback specific changes while keeping others
git checkout develop
git revert <specific-commit-hash>
git push origin develop
```

### Database Rollback
```bash
# If database issues arise
python manage.py migrate <app_name> <previous_migration>
```

## Monitoring & Validation

### Automated Checks
```bash
#!/bin/bash
# post-deployment-check.sh

echo "Running post-deployment validation..."

# Health check
curl -f http://localhost:8000/health/ || exit 1

# API endpoints check
curl -f http://localhost:8000/api/v1/ || exit 1

# Admin check
curl -f http://localhost:8000/django-admin/ || exit 1

# Database connectivity
python manage.py dbshell --command="\q" || exit 1

echo "All checks passed!"
```

### Manual Validation Checklist
- [ ] All API endpoints respond correctly
- [ ] Django admin interface loads
- [ ] User authentication works
- [ ] Content CRUD operations work
- [ ] Search functionality works
- [ ] File uploads work
- [ ] Email notifications work

### Performance Monitoring
- Response time baselines
- Memory usage patterns
- Database query performance
- Error rate monitoring

## Communication Plan

### Team Communication
- **Week 1:** Share restructure plan, get feedback
- **Week 2:** Begin implementation, daily updates
- **Week 3:** Staging deployment, final review
- **Week 4:** Production deployment, monitoring

### Stakeholder Updates
- Pre-migration briefing
- Progress reports during migration
- Post-migration summary report
- Performance impact analysis

## Success Criteria

### Technical Success
- [ ] All existing functionality preserved
- [ ] No increase in response times
- [ ] No increase in error rates
- [ ] All tests passing
- [ ] Deployment pipeline functional

### Code Quality Success
- [ ] Reduced code duplication
- [ ] Improved maintainability metrics
- [ ] Faster development setup
- [ ] Clearer code organization
- [ ] Better test coverage

### Team Success
- [ ] Reduced onboarding time for new developers
- [ ] Faster feature development
- [ ] Easier debugging and troubleshooting
- [ ] Improved code review efficiency

---

**Remember:** The goal is improvement without risk. Every step should be reversible, and system stability is the top priority.
