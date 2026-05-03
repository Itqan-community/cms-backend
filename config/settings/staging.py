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
SESSION_COOKIE_DOMAIN = ".itqan.dev"
CSRF_COOKIE_DOMAIN = ".itqan.dev"
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
# Feature flags
# ============================================================

ENABLE_DEBUG_TOOLBAR = False  # Disable even in staging for security
ENABLE_API_DOCS = True  # Keep API docs available in staging
