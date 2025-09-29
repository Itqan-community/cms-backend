# Django Project Restructure - Implementation Checklist

## Phase 1: Legacy Cleanup (HIGH PRIORITY)

### 1.1 Directory Cleanup
- [ ] **Backup current structure** (create git branch: `backup/pre-restructure`)
- [ ] **Remove duplicate `core/`**
  - [ ] Verify no unique code exists in `core/`
  - [ ] Remove directory: `rm -rf core/`
  - [ ] Update any imports that reference old `core.`
- [ ] **Remove legacy `itqan_cms/`**
  - [ ] Verify all functionality moved to `config/`
  - [ ] Remove directory: `rm -rf itqan_cms/`
  - [ ] Search and replace any remaining `itqan_cms` imports
- [ ] **Clean up unused apps**
  - [ ] Analyze `developers/` - remove if empty
  - [ ] Analyze `publishers/` - merge into `content` or remove
  - [ ] Analyze `resources/` - merge into `content` or remove
  - [ ] Update `INSTALLED_APPS` in settings

### 1.2 Import Statement Updates
- [ ] **Search for old imports**
  ```bash
  grep -r "from itqan_cms" /
  grep -r "import itqan_cms" /
  grep -r "from core\." /
  ```
- [ ] **Update all references to use `config.*`**

## Phase 2: App Standardization (HIGH PRIORITY)

### 2.1 Create Missing URL Files
- [ ] **Create `apps/content/urls.py`**
  - [ ] Add app_name = 'content'
  - [ ] Define resource and category URL patterns
  - [ ] Include workflow endpoints
- [ ] **Create `apps/licensing/urls.py`**
  - [ ] Add license management endpoints
  - [ ] Add access request endpoints
- [ ] **Create `apps/analytics/urls.py`**
  - [ ] Add analytics endpoints
- [ ] **Create `apps/search/urls.py`**
  - [ ] Add search endpoints
  - [ ] Add indexing endpoints

### 2.2 Update Main URL Configuration
- [ ] **Update `config/urls.py`**
  - [ ] Group API endpoints under versioned paths
  - [ ] Add proper namespacing with include()
  - [ ] Organize by logical sections
  - [ ] Test all URL patterns resolve correctly

### 2.3 Standardize App Structure
- [ ] **For each app, ensure these files exist:**
  - [ ] `__init__.py`
  - [ ] `apps.py` (with correct `name = 'apps.appname'`)
  - [ ] `models.py`
  - [ ] `views.py` (or `views/` directory)
  - [ ] `admin.py`
  - [ ] `urls.py` (newly created)
  - [ ] `serializers.py` (for API apps)
  - [ ] `tests.py` (or `tests/` directory)
  - [ ] `migrations/` directory

### 2.4 Large App Modularization
- [ ] **Split `apps/content/` if it becomes too large:**
  - [ ] Create `models/` directory with separate model files
  - [ ] Create `views/` directory with separate view files
  - [ ] Create `serializers/` directory
  - [ ] Update imports in `__init__.py` files

## Phase 3: Environment Configuration (MEDIUM PRIORITY)

### 3.1 Create Missing Environment Files
- [ ] **Create `config/settings/testing.py`**
  - [ ] Inherit from base.py
  - [ ] Configure test database
  - [ ] Disable unnecessary features for testing
- [ ] **Update `config/settings/__init__.py`**
  - [ ] Add environment detection logic
  - [ ] Test environment switching works

### 3.2 Environment Variables
- [ ] **Standardize environment variable usage**
  - [ ] Document required variables for each environment
  - [ ] Update deployment scripts to use `DJANGO_ENV`
  - [ ] Test environment switching in Docker

## Phase 4: Shared Libraries (MEDIUM PRIORITY)

### 4.1 Create Libraries Structure
- [ ] **Create `libs/` directory**
- [ ] **Create subdirectories:**
  - [ ] `libs/auth/` - Authentication utilities
  - [ ] `libs/storage/` - Storage backends
  - [ ] `libs/search/` - Search integrations
  - [ ] `libs/validation/` - Custom validators
  - [ ] `libs/middleware/` - Custom middleware
  - [ ] `libs/utils/` - Common utilities

### 4.2 Extract Common Code
- [ ] **Move reusable authentication code to `libs/auth/`**
- [ ] **Move storage utilities to `libs/storage/`**
- [ ] **Move common validators to `libs/validation/`**
- [ ] **Update imports across all apps**

## Phase 5: Testing Structure (MEDIUM PRIORITY)

### 5.1 Project-Level Testing
- [ ] **Create `tests/` directory at project root**
- [ ] **Create `tests/conftest.py` for pytest configuration**
- [ ] **Create `tests/factories/` for model factories**
- [ ] **Create test subdirectories by type:**
  - [ ] `tests/unit/`
  - [ ] `tests/integration/`
  - [ ] `tests/e2e/`

### 5.2 App-Level Testing Enhancement
- [ ] **For complex apps, create `tests/` directories:**
  - [ ] `apps/content/tests/`
  - [ ] `apps/accounts/tests/`
  - [ ] `apps/licensing/tests/`
- [ ] **Split test files by functionality:**
  - [ ] `test_models.py`
  - [ ] `test_views.py`
  - [ ] `test_api.py`
  - [ ] `test_serializers.py`

## Phase 6: Documentation (LOW PRIORITY)

### 6.1 Architecture Documentation
- [ ] **Create API documentation structure**
- [ ] **Document deployment procedures**
- [ ] **Create development setup guide**
- [ ] **Document architecture decisions**

## Validation Checklist

### After Each Phase
- [ ] **Run all tests:** `python manage.py test`
- [ ] **Check migrations:** `python manage.py makemigrations --check`
- [ ] **Verify server starts:** `python manage.py runserver`
- [ ] **Test API endpoints** with Postman/curl
- [ ] **Check Django admin** functionality
- [ ] **Verify deployment** in development environment

### Pre-Production Checklist
- [ ] **All tests passing**
- [ ] **No migration conflicts**
- [ ] **All URL patterns working**
- [ ] **Environment switching functional**
- [ ] **Docker builds successfully**
- [ ] **Deployment scripts updated**

## Rollback Plan

### If Issues Arise
1. **Checkout backup branch:** `git checkout backup/pre-restructure`
2. **Identify specific issue** that caused rollback
3. **Create targeted fix** on feature branch
4. **Test fix thoroughly** before re-applying
5. **Apply changes incrementally** rather than all at once

## Success Metrics

### Technical Metrics
- [ ] Reduced code duplication
- [ ] Improved import clarity
- [ ] Faster test execution
- [ ] Easier navigation for developers
- [ ] Simplified deployment process

### Developer Experience Metrics
- [ ] New developer onboarding time reduced
- [ ] Code review efficiency improved
- [ ] Bug resolution time decreased
- [ ] Feature development velocity increased

---

**Note:** This checklist should be executed incrementally, with thorough testing after each major change. Consider using feature branches for each phase to enable easy rollback if needed.
