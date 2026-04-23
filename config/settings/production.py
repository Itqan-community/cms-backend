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
    "https://saudi-recitation-center.netlify.app",
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
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://localhost:6379/1"),
    }
}

# ============================================================
# Celery (uses RabbitMQ broker + Redis result backend)
# ============================================================

CELERY_TASK_ALWAYS_EAGER = False


# ============================================================
# CSRF
# ============================================================

CSRF_TRUSTED_ORIGINS = [
    "https://api.cms.itqan.dev",
    "https://cms.itqan.dev",
    "https://saudi-recitation-center.netlify.app",
    "http://localhost:4200",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ============================================================
# Logging
# ============================================================

settings.LOGGING["handlers"]["console"]["level"] = "INFO"
settings.LOGGING["root"]["level"] = "INFO"

# ============================================================
# Django-Allauth
# ============================================================

ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

# ============================================================
# Email
# ============================================================

_EMAIL_SENDER_NAME: str = config("EMAIL_SENDER_NAME", default="")
_EMAIL_SENDER_EMAIL: str = config("EMAIL_SENDER_EMAIL", default="")

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", cast=int, default=587)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
DEFAULT_FROM_EMAIL = f"{_EMAIL_SENDER_NAME} <{_EMAIL_SENDER_EMAIL}>" if _EMAIL_SENDER_NAME else _EMAIL_SENDER_EMAIL

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
