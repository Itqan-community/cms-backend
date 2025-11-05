"""
Itqan CMS - Production Settings
"""

from .base import *  # noqa: F403, F401

# Production-specific settings
DEBUG = False

ALLOWED_HOSTS = [
    "api.cms.itqan.dev",
    "cms.itqan.dev",
    "develop.api.cms.itqan.dev",
]

# Production security settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings for production
CORS_ALLOWED_ORIGINS = [
    "https://cms.itqan.dev",
    "https://develop.cms.itqan.dev",
    "https://itqan-cms.netlify.app",
]
CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = [
    "https://api.cms.itqan.dev",
    "https://cms.itqan.dev",
    "https://develop.api.cms.itqan.dev",
    "https://develop.cms.itqan.dev",
    "https://itqan-cms.netlify.app",
]

# Production cache configuration (using Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": config("REDIS_URL", "redis://redis:6379/1"),  # noqa: F405
    }
}

# Production database configuration
DATABASES["default"].update(  # noqa: F405
    {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
)

# Static and Media files configuration for production using OSS (MinIO/S3)
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
    },
}

# OSS Configuration (MinIO/S3 compatible)
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = False
AWS_S3_VERIFY = True
AWS_S3_USE_SSL = True
AWS_S3_ADDRESSING_STYLE = "virtual"

AWS_S3_ENDPOINT_URL = config("OSS_ENDPOINT_URL", "")  # noqa: F405
AWS_ACCESS_KEY_ID = config("OSS_ACCESS_KEY_ID", "")  # noqa: F405
AWS_SECRET_ACCESS_KEY = config("OSS_SECRET_ACCESS_KEY", "")  # noqa: F405
AWS_STORAGE_BUCKET_NAME = config("OSS_BUCKET_NAME", "itqan-cms")  # noqa: F405
AWS_S3_REGION_NAME = config("OSS_REGION", "oss-me-east-1")  # noqa: F405
AWS_S3_CUSTOM_DOMAIN = config("OSS_CUSTOM_DOMAIN", "")  # noqa: F405
AWS_DEFAULT_ACL = "public-read"
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "max-age=86400",
}

# Static files URL
if AWS_S3_CUSTOM_DOMAIN:
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
else:
    STATIC_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/static/"
    MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{AWS_STORAGE_BUCKET_NAME}/media/"

# Celery configuration for production
CELERY_BROKER_URL = config("CELERY_BROKER_URL", "redis://redis:6379/0")  # noqa: F405
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", "redis://redis:6379/0")  # noqa: F405
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = False

# Production email configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", "smtp.mailgun.org")  # noqa: F405
EMAIL_PORT = config("EMAIL_PORT", 587, cast=int)  # noqa: F405
EMAIL_HOST_USER = config("EMAIL_HOST_USER", "")  # noqa: F405
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", "")  # noqa: F405
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", "noreply@itqan.com")  # noqa: F405

LOGGING["handlers"]["console"]["level"] = "WARNING"  # noqa: F405
LOGGING["root"]["level"] = "INFO"  # noqa: F405

# Force HTTPS in allauth callback URLs
