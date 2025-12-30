"""
Itqan CMS - Development Settings
"""

import importlib.util

from django.conf import settings

from .base import *  # noqa: F401, F403

# =========================
# General
# =========================

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "::1",
    "develop.api.cms.itqan.dev",
]

# =========================
# Middleware
# =========================
# Ensure the security middleware is first.
# (Use settings.* to avoid F405 from star-import.)
if hasattr(settings, "MIDDLEWARE") and isinstance(settings.MIDDLEWARE, list):
    settings.MIDDLEWARE.insert(0, "django.middleware.security.SecurityMiddleware")

# =========================
# Cache (dummy for dev)
# =========================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# =========================
# Celery (eager for dev)
# =========================
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# =========================
# Email / CORS / CSRF
# =========================
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"

CORS_ALLOW_ALL_ORIGINS = True  # Dev only
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "https://develop.api.cms.itqan.dev",
    "https://develop.cms.itqan.dev",
    "https://staging.cms.itqan.dev",
    "https://staging--itqan-cms.netlify.app",
    "https://cms.itqan.dev",
    "https://itqan-cms.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# =========================
# Security (relaxed for dev)
# =========================
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_BROWSER_XSS_FILTER = False
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# =========================
# File Storage (local for development)
# =========================
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# =========================
# OAuth providers (DB-backed)
# =========================
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

# =========================
# Debug Toolbar (optional)
# =========================
if importlib.util.find_spec("debug_toolbar"):
    settings.INSTALLED_APPS.append("debug_toolbar")
    # Place it right after the security middleware if present
    insert_at = 1 if "django.middleware.security.SecurityMiddleware" in settings.MIDDLEWARE else 0
    settings.MIDDLEWARE.insert(insert_at, "debug_toolbar.middleware.DebugToolbarMiddleware")
