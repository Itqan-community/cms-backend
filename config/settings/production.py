"""
Itqan CMS - Production Settings
"""

from decouple import config
from django.conf import settings

from .base import *  # noqa: F401, F403

# ============================================================
# General
# ============================================================

DEBUG = False

ALLOWED_HOSTS = [
    "api.cms.itqan.dev",  # Production API domain
    "develop.api.cms.itqan.dev",  # Development environment
    "staging.api.cms.itqan.dev",  # Staging environment
    "localhost",  # For local Docker development
]

# ============================================================
# Security
# ============================================================

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# ============================================================
# CORS
# ============================================================

CORS_ALLOWED_ORIGINS = [
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "https://develop.cms.itqan.dev",
    "https://develop--itqan-cms.netlify.app",
    "https://staging.cms.itqan.dev",
    "https://staging--itqan-cms.netlify.app",
    # Local frontend development
    "http://localhost:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ============================================================
# Database
# ============================================================

settings.DATABASES["default"].update(
    {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "sslmode": "require",
            "connect_timeout": 10,
        },
    }
)

# ============================================================
# Cache
# ============================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# ============================================================
# Celery
# ============================================================

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ============================================================
# File Storage (Alibaba OSS)
# ============================================================

DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

AWS_S3_ENDPOINT_URL = config("OSS_ENDPOINT_URL", "")
AWS_ACCESS_KEY_ID = config("OSS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = config("OSS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = config("OSS_BUCKET_NAME", "itqan-cms")
AWS_S3_REGION_NAME = config("OSS_REGION", "oss-me-east-1")
AWS_S3_CUSTOM_DOMAIN = config("OSS_CUSTOM_DOMAIN", "")
AWS_DEFAULT_ACL = "public-read"
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    "https://api.cms.itqan.dev",
    "https://develop.cms.itqan.dev",
    "https://develop--itqan-cms.netlify.app",
    "https://staging.cms.itqan.dev",
    "https://staging--itqan-cms.netlify.app",
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ============================================================
# Email
# ============================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", "smtp.mailgun.org")
EMAIL_PORT = config("EMAIL_PORT", 587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", "noreply@itqan.com")

# ============================================================
# Logging
# ============================================================

settings.LOGGING["handlers"]["console"]["level"] = "WARNING"
settings.LOGGING["root"]["level"] = "INFO"

# ============================================================
# Django-Allauth
# ============================================================

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
    },
    "github": {
        "SCOPE": ["user:email"],
        "VERIFIED_EMAIL": True,
    },
}
