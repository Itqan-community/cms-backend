
"""
Itqan CMS - Production Settings
"""
from .base import *

# Production-specific settings
DEBUG = False

ALLOWED_HOSTS = [
    'api.itqan.com',
    'cms.itqan.com',
    '.itqan.com',  # Wildcard subdomain
    'api.cms.itqan.dev',  # Production API domain
    'develop.api.cms.itqan.dev',  # Development environment
    'staging.api.cms.itqan.dev',  # Staging environment  
    'localhost',  # For local Docker development
]

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Production CORS settings
CORS_ALLOWED_ORIGINS = [
    "https://cms.itqan.com",
    "https://api.itqan.com",
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "https://develop.cms.itqan.dev",
    "https://develop--itqan-cms.netlify.app",
    "https://staging.cms.itqan.dev",
    "https://staging--itqan-cms.netlify.app",
    # Local frontend development
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Production database configuration
DATABASES['default'].update({
    'ENGINE': 'django.db.backends.postgresql',
    'CONN_MAX_AGE': 60,
    'OPTIONS': {
        'sslmode': 'require',
        'connect_timeout': 10,
    },
})

# Production cache configuration - Using dummy cache for now (no Redis in docker-compose)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Disable Celery for now (no Redis broker available)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Production file storage (Alibaba OSS)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

AWS_S3_ENDPOINT_URL = config('OSS_ENDPOINT_URL', '')
AWS_ACCESS_KEY_ID = config('OSS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = config('OSS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = config('OSS_BUCKET_NAME', 'itqan-cms')
AWS_S3_REGION_NAME = config('OSS_REGION', 'oss-me-east-1')
AWS_S3_CUSTOM_DOMAIN = config('OSS_CUSTOM_DOMAIN', '')
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# CSRF trusted origins for production
CSRF_TRUSTED_ORIGINS = [
    'https://api.cms.itqan.dev',
    'https://cms.itqan.com',
    'https://*.itqan.com',
    'https://develop.cms.itqan.dev',
    'https://develop--itqan-cms.netlify.app',
    'https://staging.cms.itqan.dev',
    'https://staging--itqan-cms.netlify.app',
    'https://cms.itqan.dev',
    'https://itqan-cms.netlify.app',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]

# Production email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', 'smtp.mailgun.org')
EMAIL_PORT = config('EMAIL_PORT', 587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', 'noreply@itqan.com')

# Production logging
# Write logs to an application directory that exists in the container
LOGGING['handlers']['file']['filename'] = '/app/logs/django.log'
LOGGING['handlers']['console']['level'] = 'WARNING'
LOGGING['root']['level'] = 'INFO'

# Error monitoring (Sentry)
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=config('SENTRY_DSN', ''),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=True,
        environment='production',
    )
except ImportError:
    # Sentry SDK not installed or configured; skipping error monitoring
    pass

# Production Wagtail settings
WAGTAIL_CACHE = True
WAGTAILADMIN_BASE_URL = 'https://cms.itqan.com'

# Force HTTPS in allauth callback URLs
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'

# Social auth settings for production (use database configuration only)
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
