"""
Itqan CMS - Staging Settings
"""
from .base import *

# Staging-specific settings
DEBUG = False  # Production-like behavior but with more verbose logging

ALLOWED_HOSTS = [
    'staging.api.cms.itqan.dev',  # Staging environment
    'localhost',  # For local Docker development
]

# Security settings for staging (similar to production but less strict)
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Staging database configuration
DATABASES.update({
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': {
            'sslmode': 'require',
            'connect_timeout': 10,
        },
    }
})

# CSRF trusted origins for staging
CSRF_TRUSTED_ORIGINS = [
    'https://staging.api.cms.itqan.dev',
    'https://staging.cms.itqan.dev',
    'https://staging--itqan-cms.netlify.app',
    'https://develop.api.cms.itqan.dev',
    'https://develop.cms.itqan.dev',
    'https://develop--itqan-cms.netlify.app',
    'https://cms.itqan.dev',
    'https://itqan-cms.netlify.app',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Force HTTPS in allauth callback URLs
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# Staging cache configuration - Using dummy cache for now (no Redis in docker-compose)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable Celery for staging (no Redis broker available)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Staging file storage (local filesystem for now)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Staging media and static files
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'

# Email configuration for staging
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Log emails to console
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', 'staging-noreply@itqan.dev')

LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['root']['level'] = 'INFO'

# Django-allauth settings for staging
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_RATE_LIMITS = 'login_failed'

# Social auth settings for staging (use database configuration only)
# OAuth apps are configured via Django admin for better security and flexibility
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
    },
    'github': {
        'SCOPE': [
            'user:email',
        ],
        'VERIFIED_EMAIL': True,
    }
}

# CORS settings for staging
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://staging.cms.itqan.dev",  # Staging frontend
    "https://staging--itqan-cms.netlify.app",
    "https://develop.cms.itqan.dev",
    "https://develop--itqan-cms.netlify.app",
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "http://localhost:4200",  # Angular dev server
    "http://localhost:3000",  # Local frontend development
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# Staging-specific settings

# API Rate limiting for staging (more lenient than production)
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100/hour',
    'user': '1000/hour',
    'login': '10/minute',
}

# Staging-specific feature flags
ENABLE_DEBUG_TOOLBAR = False  # Disable even in staging for security
ENABLE_API_DOCS = True  # Keep API docs available in staging
