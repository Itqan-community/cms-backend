"""
Itqan CMS - Staging Settings
"""

from decouple import config
from django.conf import settings

from .base import *  # noqa: F401, F403

# ============================================================
# General
# ============================================================

# Production-like behavior but with more verbose logging
DEBUG = False

ALLOWED_HOSTS = [
    "staging.api.cms.itqan.dev",  # Staging environment
    "localhost",  # For local Docker development
]

# ============================================================
# Security (staging; slightly less strict than prod)
# ============================================================

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# ============================================================
# Database
# ============================================================

settings.DATABASES.update(
    {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST"),
            "PORT": config("DB_PORT"),
            "OPTIONS": {
                "sslmode": "require",
                "connect_timeout": 10,
            },
        }
    }
)

# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    "https://staging--saudi-recitation-center.netlify.app",
    "https://staging.cms.itqan.dev",  # Staging frontend
    "https://staging--itqan-cms.netlify.app",
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "http://localhost:4200",  # Angular dev server
    "http://localhost:3000",  # Local frontend development
    "http://127.0.0.1:3000",
]

# Force HTTPS in allauth callback URLs
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# ============================================================
# Cache
# ============================================================

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# ============================================================
# Celery (uses RabbitMQ broker + Redis result backend)
# ============================================================

CELERY_TASK_ALWAYS_EAGER = False

# Media / Static
MEDIA_URL = "/media/"
MEDIA_ROOT = "/app/media"
STATIC_URL = "/static/"
STATIC_ROOT = "/app/staticfiles"

# ============================================================
# Logging
# ============================================================

settings.LOGGING["handlers"]["console"]["level"] = "INFO"
settings.LOGGING["root"]["level"] = "INFO"

# ============================================================
# Django-Allauth
# ============================================================

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_RATE_LIMITS = "login_failed"

# OAuth apps are configured via Django admin for better security and flexibility
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

# ============================================================
# CORS
# ============================================================

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = CSRF_TRUSTED_ORIGINS
CORS_ALLOW_CREDENTIALS = True

# ============================================================
# DRF
# ============================================================

# API Rate limiting for staging (more lenient than production)
settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "100/hour",
    "user": "1000/hour",
    "login": "10/minute",
}

# ============================================================
# Email (sandbox)
# ============================================================

_EMAIL_SENDER_NAME: str = config("STAGING_EMAIL_SENDER_NAME", default="")
_EMAIL_SENDER_EMAIL: str = config("STAGING_EMAIL_SENDER_EMAIL", default="")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("STAGING_EMAIL_HOST", default="")
EMAIL_PORT = config("STAGING_EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("STAGING_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("STAGING_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = f"{_EMAIL_SENDER_NAME} <{_EMAIL_SENDER_EMAIL}>" if _EMAIL_SENDER_NAME else _EMAIL_SENDER_EMAIL

# ============================================================
# Feature flags
# ============================================================

ENABLE_DEBUG_TOOLBAR = False  # Disable even in staging for security
ENABLE_API_DOCS = True  # Keep API docs available in staging
