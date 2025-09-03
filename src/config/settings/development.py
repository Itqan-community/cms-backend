"""
Itqan CMS - Development Settings
"""
from .base import *

# Development-specific settings
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', 'develop.api.cms.itqan.dev']

# Additional development apps
# INSTALLED_APPS += [
#     'django_extensions',  # Install if needed: pip install django-extensions
# ]

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

# Development CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # Only for development
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins for development
CSRF_TRUSTED_ORIGINS = [
    'https://develop.api.cms.itqan.dev',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
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

# Wagtail development settings
WAGTAILADMIN_BASE_URL = 'http://localhost:8000'

# Django Debug Toolbar (if installed)
try:
    import debug_toolbar
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')
except ImportError:
    pass
