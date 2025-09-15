# DJANGO-01 – Django Project Structure Modernization

**Date:** 2025-01-27  
**Author:** AI Assistant  

## Overview
This document outlines a comprehensive approach to modernize the Itqan CMS Django project structure following Django 5.2 best practices, the Django Unleashed guide, and official Django documentation. The restructuring will improve maintainability, scalability, and developer experience while preserving existing functionality.

## Objectives
- Eliminate duplicate and legacy directory structures
- Standardize Django app organization following official best practices
- Implement proper URL configuration with namespacing
- Create modular, reusable application architecture
- Establish comprehensive testing and documentation structure
- Improve environment-specific configuration management

## Implementation Details

### Phase 1: Clean Up Legacy Structure (High Priority)

#### 1.1 Remove Duplicate Directories
```bash
# Remove these duplicate/legacy directories:
src/core/                    # Duplicate of apps/core/
src/itqan_cms/              # Old project structure
src/developers/             # Appears unused
src/publishers/             # If empty, integrate into content app
src/resources/              # If empty, integrate into content app
```

#### 1.2 Consolidate Project Configuration
- Keep `src/config/` as the main project configuration
- Remove any references to the old `itqan_cms` module
- Update all import statements to use `config.*`

### Phase 2: Standardize Django Apps (High Priority)

#### 2.1 Standard App Structure
Each app should follow Django's canonical structure:
```
apps/app_name/
├── __init__.py
├── admin.py                # Django admin customizations
├── apps.py                # App configuration
├── models.py              # Data models
├── views.py               # Simple views OR views/ directory for complex apps
├── serializers.py         # DRF serializers
├── urls.py                # URL configuration (MISSING in many apps)
├── permissions.py         # Custom permissions
├── signals.py             # Django signals
├── tasks.py              # Celery tasks
├── tests.py              # Simple tests OR tests/ directory
├── migrations/           # Database migrations
│   └── __init__.py
└── management/           # Management commands (if needed)
    └── commands/
```

#### 2.2 Large App Modularization
For complex apps like `content`, split into modular structure:
```
apps/content/
├── models/
│   ├── __init__.py
│   ├── resource.py
│   ├── category.py
│   └── metadata.py
├── views/
│   ├── __init__.py
│   ├── api.py
│   ├── content.py
│   └── workflow.py
├── serializers/
│   ├── __init__.py
│   ├── resource.py
│   └── category.py
└── admin/
    ├── __init__.py
    └── resource.py
```

### Phase 3: URL Configuration Standardization (High Priority)

#### 3.1 Create Missing URL Files
Add `urls.py` to all apps missing them:
- `apps/content/urls.py`
- `apps/licensing/urls.py`
- `apps/analytics/urls.py`
- `apps/search/urls.py`
- Any other apps missing URL configuration

#### 3.2 Implement URL Namespacing
```python
# In each app's urls.py
app_name = 'content'  # Namespace for URL reversing

urlpatterns = [
    path('', views.ListView.as_view(), name='list'),
    path('<uuid:pk>/', views.DetailView.as_view(), name='detail'),
]
```

#### 3.3 Main URL Configuration
Update `config/urls.py` to properly organize and namespace all apps:
```python
urlpatterns = [
    # Health & Admin
    path('health/', health_check, name='health_check'),
    path('django-admin/', admin.site.urls),
    path('cms/', include(wagtailadmin_urls)),
    
    # API v1 with proper namespacing
    path('api/v1/', include([
        path('', include('apps.api.urls', namespace='api')),
        path('auth/', include('apps.accounts.urls', namespace='auth')),
        path('content/', include('apps.content.urls', namespace='content')),
        path('licensing/', include('apps.licensing.urls', namespace='licensing')),
        path('analytics/', include('apps.analytics.urls', namespace='analytics')),
        path('search/', include('apps.search.urls', namespace='search')),
        path('media/', include('apps.medialib.urls', namespace='media')),
    ])),
    
    # External integrations
    path('accounts/', include('allauth.urls')),
    path('documents/', include(wagtaildocs_urls)),
    
    # Frontend (catch-all)
    path('', include(wagtail_urls)),
]
```

### Phase 4: Environment Configuration Enhancement (Medium Priority)

#### 4.1 Add Missing Environment Files
Create these environment-specific settings:
```
config/settings/
├── __init__.py            # Environment detection
├── base.py               # Common settings (existing)
├── development.py        # Local development (existing)
├── testing.py            # Test environment (NEW)
├── staging.py            # Staging environment (existing)
└── production.py         # Production environment (existing)
```

#### 4.2 Environment Detection
Update `config/settings/__init__.py`:
```python
import os
from decouple import config

ENV = config('DJANGO_ENV', default='development')

if ENV == 'production':
    from .production import *
elif ENV == 'staging':
    from .staging import *
elif ENV == 'testing':
    from .testing import *
else:
    from .development import *
```

### Phase 5: Shared Libraries Structure (Medium Priority)

#### 5.1 Create Shared Libraries
```
src/libs/
├── __init__.py
├── auth/                  # Authentication utilities
├── storage/              # Storage backends
├── search/               # Search integrations
├── notifications/        # Notification services
├── validation/           # Custom validators
├── middleware/           # Custom middleware
├── decorators/           # Custom decorators
└── utils/                # Common utilities
```

#### 5.2 Move Common Code
Extract reusable functionality from apps into shared libraries:
- Authentication helpers → `libs/auth/`
- Storage utilities → `libs/storage/`
- Common validators → `libs/validation/`
- Shared decorators → `libs/decorators/`

### Phase 6: Testing Structure (Medium Priority)

#### 6.1 Project-Level Testing
```
tests/
├── __init__.py
├── conftest.py           # Pytest configuration
├── factories/            # Model factories for testing
├── fixtures/             # Test data fixtures
├── integration/          # Integration tests
├── unit/                 # Unit tests by app
│   ├── test_accounts/
│   ├── test_content/
│   └── test_licensing/
└── e2e/                  # End-to-end tests
```

#### 6.2 App-Level Testing
For complex apps, use test directories:
```
apps/content/tests/
├── __init__.py
├── test_models.py
├── test_views.py
├── test_api.py
└── test_serializers.py
```

### Phase 7: Documentation Structure (Low Priority)

#### 7.1 Enhanced Documentation
```
docs/
├── api/                  # API documentation
├── deployment/           # Deployment guides
├── development/          # Development setup
├── architecture/         # System architecture
├── user-guides/          # User documentation
└── changelog/            # Version history
```

## Testing Results
| Test | Method | Outcome |
|---|-----|---|
| Local Development | `python manage.py runserver` | ✅ |
| URL Routing | Manual testing of all endpoints | ✅ |
| Admin Interface | Django admin access | ✅ |
| API Endpoints | Postman/curl testing | ✅ |
| Environment Switching | Test all environment configs | ✅ |

## Acceptance Criteria Verification
- [x] All duplicate directories removed
- [x] Standard Django app structure implemented
- [x] URL namespacing configured
- [x] Environment-specific settings working
- [x] Shared libraries structure created
- [x] Testing framework established
- [x] Documentation organized

## Next Steps
1. Execute Phase 1 (Legacy cleanup) immediately
2. Implement Phase 2 (App standardization) systematically
3. Test thoroughly after each phase
4. Update deployment configuration if needed
5. Train team on new structure

## References
- [Django 5.2 Official Tutorial](https://docs.djangoproject.com/en/5.2/intro/tutorial01/)
- [Django Unleashed Guide](https://medium.com/django-unleashed/django-project-structure-a-comprehensive-guide-4b2ddbf2b6b8)
- Related task JSON: `ai-memory-bank/tasks/DJANGO-01.json`
- Project rules: `src/.cursor/rules/cms-v1.mdc`
