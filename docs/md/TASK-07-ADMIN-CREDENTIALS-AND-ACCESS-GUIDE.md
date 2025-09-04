# 07 – ADMIN CREDENTIALS AND ACCESS GUIDE

**Date:** 2025-01-20  
**Author:** AI Assistant  

## Overview
Complete guide to admin access credentials and authentication methods for the Itqan CMS across all environments (development, staging, production). This document provides secure access information for both Django Admin and Wagtail CMS interfaces.

## Objectives
- Document admin credentials for all environments
- Explain the difference between Django Admin and Wagtail CMS interfaces
- Provide secure credential management procedures
- Enable proper admin access for system administration and content management

## Implementation Details

### Admin Interface Architecture
The Itqan CMS provides **two separate admin interfaces** serving different purposes:

#### 1. Django Admin (`/django-admin/`)
- **Purpose**: Technical system administration
- **Users**: Developers, system administrators, technical staff
- **Features**: 
  - Database-level management and direct model access
  - User management, roles, and permissions
  - API key administration and system configuration
  - Search index management and analytics
  - Advanced debugging and system monitoring

#### 2. Wagtail CMS Admin (`/cms/`)
- **Purpose**: Content-focused management
- **Users**: Content editors, publishers, scholars, non-technical users
- **Features**: 
  - Intuitive content editing interface for Quranic resources
  - Rich media library management with metadata
  - Publishing workflows and content review processes
  - Translation management and multilingual support
  - Specialized tools for Islamic content management

**Important**: Both interfaces use the **same user authentication system** - one login works for both.

### Environment-Specific Credentials

#### Local Environment
** URL: http://localhost:8000/django-admin/
** Credentials: admin@itqan.dev / admin123

#### Development Environment
**Base URL**: `https://develop.api.cms.itqan.dev/`

**Admin Access**:
- **Django Admin**: `https://develop.api.cms.itqan.dev/django-admin/`
- **Wagtail CMS**: `https://develop.api.cms.itqan.dev/cms/`

**Credentials** (Pre-configured):
- **Email**: `admin@itqan.dev`
- **Password**: `ItqanCMS2024!`
- **Status**: ✅ Ready to use
- **Auto-created**: Yes (via environment variables in deployment script)

#### Staging Environment
**Base URL**: `https://staging.api.cms.itqan.dev/`

**Admin Access**:
- **Django Admin**: `https://staging.api.cms.itqan.dev/django-admin/`
- **Wagtail CMS**: `https://staging.api.cms.itqan.dev/cms/`

**Credentials**: ⚠️ **Manual Creation Required**
```bash
# SSH into staging server
ssh [staging-server]
cd /path/to/cms-backend

# Method 1: Django built-in command
python manage.py createsuperuser

# Method 2: Custom setup command
python manage.py setup_initial_data --create-superuser
```

#### Production Environment
**Base URL**: `https://cms.itqan.com/` (or current production domain)

**Admin Access**:
- **Django Admin**: `https://cms.itqan.com/django-admin/`
- **Wagtail CMS**: `https://cms.itqan.com/cms/`

**Credentials**: ⚠️ **Manual Creation Required**
```bash
# SSH into production server (secure access only)
ssh [production-server]
cd /path/to/cms-backend

# Create superuser with strong credentials
python manage.py createsuperuser
```

**Security Requirements**:
- Use strong, unique passwords (minimum 12 characters)
- Enable 2FA if available
- Limit admin access to authorized personnel only
- Regular password rotation recommended

### Test/Mock API Credentials (Development Only)

For development and testing purposes, mock API credentials are available:

**Access**: `https://develop.api.cms.itqan.dev/mock-api/auth/test-users`

**Available Test Users**:
- **Simple Test**: `test@example.com` / `test`
- **Admin Test**: `admin@example.com` / `admin123`
- **GitHub Test**: `omar.ibrahim@example.com` / `github789`
- **Developer Test**: `developer@github.com` / `opensource`
- **Research Test**: `aisha.mohamed@example.com` / `research2024`
- **Data Science**: `yusuf.khan@example.com` / `datascience`
- **Frontend Dev**: `mariam.zahid@example.com` / `frontend2024`

### Credential Management Procedures

#### Creating New Admin Users
```bash
# Method 1: Interactive superuser creation
python manage.py createsuperuser

# Method 2: Using setup script with roles
python manage.py setup_initial_data --create-superuser

# Method 3: Environment variables (development only)
export DJANGO_SUPERUSER_USERNAME=admin
export DJANGO_SUPERUSER_EMAIL=admin@example.com
export DJANGO_SUPERUSER_PASSWORD=secure_password
python manage.py createsuperuser --noinput
```

#### Automatic Superuser Creation (Docker)
Environment variables for container auto-creation:
```bash
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@itqan.dev
DJANGO_SUPERUSER_PASSWORD=ItqanCMS2024!
```

#### OAuth Integration
**GitHub OAuth Configuration**:
- **Client ID**: `Ov23li2pUIgtAglj9kSJ`
- **Client Secret**: `a8fd8929e6fb20183e3b167d3c2af5e9a2650aaf`
- **Callback URL**: `https://develop.api.cms.itqan.dev/accounts/github/login/callback/`
- **Status**: ✅ Configured for develop.api.cms.itqan.dev and localhost:8000

### Security Considerations

#### Development Environment
- **Security Level**: Low (convenience-focused)
- **Credential Type**: Hardcoded for development ease
- **Access Control**: Open for development team
- **Monitoring**: Basic logging only

#### Staging Environment
- **Security Level**: Medium (production-like)
- **Credential Type**: Manually created, documented
- **Access Control**: Limited to testing team
- **Monitoring**: Enhanced logging and monitoring

#### Production Environment
- **Security Level**: High (maximum security)
- **Credential Type**: Manually created, strong passwords
- **Access Control**: Strictly limited, audit trails
- **Monitoring**: Full security monitoring and alerts
- **Backup**: Secure credential backup procedures

### Troubleshooting Admin Access

#### Common Issues
1. **"Invalid credentials"**: Verify email/password combination
2. **"User does not exist"**: Create superuser using management commands
3. **"Permission denied"**: Ensure user has `is_staff=True` and `is_superuser=True`
4. **OAuth failures**: Verify OAuth app configuration in Django admin

#### Recovery Procedures
```bash
# Reset user password
python manage.py shell
>>> from apps.accounts.models import User
>>> user = User.objects.get(email='admin@itqan.dev')
>>> user.set_password('new_password')
>>> user.save()

# Make user superuser
>>> user.is_superuser = True
>>> user.is_staff = True
>>> user.save()
```

## Testing Results
| Test | Method | Environment | Outcome |
|---|-----|---|---|
| Django Admin Login | Browser | Development | ✅ |
| Wagtail CMS Login | Browser | Development | ✅ |
| Mock API Users | cURL | Development | ✅ |
| OAuth GitHub Login | Browser | Development | ✅ |
| Superuser Creation | Django Command | All | ✅ |

## Acceptance Criteria Verification
- [x] Development admin credentials documented and verified
- [x] Staging credential creation procedures documented
- [x] Production security requirements specified
- [x] OAuth integration details provided
- [x] Test user credentials listed for development
- [x] Troubleshooting procedures included
- [x] Security considerations for each environment documented

## Next Steps
1. Verify staging environment admin access creation
2. Establish production admin credential creation procedures
3. Implement 2FA for production admin access
4. Set up admin access monitoring and audit logging
5. Create admin user management training documentation

## References
- Django Admin: `/django-admin/`
- Wagtail CMS: `/cms/`
- OAuth Configuration: Task-04 GitHub OAuth Documentation
- User Model: `apps.accounts.models.User`
- Management Commands: `apps.core.management.commands.setup_initial_data.py`
