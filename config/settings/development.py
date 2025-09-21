"""
Itqan CMS - Development Settings
"""
from .base import *

# Development-specific settings
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'develop.api.cms.itqan.dev']


# Development middleware
MIDDLEWARE.insert(0, 'django.middleware.security.SecurityMiddleware')

# Development database (configured via environment variables)

# Development cache configuration - Using dummy cache (no Redis needed)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable Celery for development (no Redis broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# Development CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # Only for development
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins for development
CSRF_TRUSTED_ORIGINS = [
    'https://develop.api.cms.itqan.dev',
    'https://develop.cms.itqan.dev',
    'https://staging.cms.itqan.dev',
    'https://staging--itqan-cms.netlify.app',
    'https://cms.itqan.dev',
    'https://itqan-cms.netlify.app',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',  # Local Django development server
    'http://127.0.0.1:8000',  # Local Django development server
]

# Development security settings (relaxed)
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Development logging
LOGGING['handlers']['console']['level'] = 'DEBUG'
LOGGING['root']['level'] = 'DEBUG'

# Additional development settings
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]

# Development-specific settings

# OAuth providers configuration for development
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
        # Removed APP configuration to rely solely on database entries
    },
    'github': {
        'SCOPE': [
            'user:email',
        ],
        'VERIFIED_EMAIL': True,
        # Removed APP configuration to rely solely on database entries
    }
}

# File storage configuration for development
# Override base.py MinIO settings to use local filesystem
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Local media settings
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Django Debug Toolbar (if installed)
try:
    import debug_toolbar
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
except ImportError:
    pass
