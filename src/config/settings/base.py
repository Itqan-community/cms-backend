"""
Itqan CMS - Base Django Settings
"""
import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = []

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for allauth
]

THIRD_PARTY_APPS = [
    'modeltranslation',  # Must be before Django apps that use translations
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Django Allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
]

LOCAL_APPS = [
    'apps.core',
    'apps.accounts',
    'apps.content',
    'apps.api',
    'apps.api_keys',
    'mock_api',  # Mock API for development and testing
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # Required for allauth
    'apps.api_keys.authentication.APIUsageMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='itqan_cms'),
        'USER': config('DB_USER', default='itqan_user'),
        'PASSWORD': config('DB_PASSWORD', default='itqan_password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 60,
        },
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ar', 'Arabic'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
}

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:4200",  # Angular development server
    "http://127.0.0.1:4200",
    # Local frontend running on port 3000
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Image file extensions for uploads
ALLOWED_IMAGE_EXTENSIONS = ['gif', 'jpg', 'jpeg', 'png', 'webp']

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files - will be overridden in environment-specific settings
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 26214400  # 25MB
FILE_UPLOAD_TEMP_DIR = None  # Use system temp dir
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# Allowed file types for uploads
ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg']
ALLOWED_FILE_EXTENSIONS = ['pdf', 'doc', 'docx', 'txt', 'zip', 'tar', 'gz', 'json', 'xml', 'csv']

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# MinIO Configuration (S3-compatible storage)
# These settings will be overridden in development/production settings
MINIO_ENDPOINT = config('MINIO_ENDPOINT', default='localhost:9000')
MINIO_ACCESS_KEY = config('MINIO_ACCESS_KEY', default='minioadmin')
MINIO_SECRET_KEY = config('MINIO_SECRET_KEY', default='minioadmin')
MINIO_USE_HTTPS = config('MINIO_USE_HTTPS', default=False, cast=bool)
MINIO_BUCKET_NAME = config('MINIO_BUCKET_NAME', default='itqan-uploads')

# Configure MinIO as S3-compatible storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# AWS S3 settings for MinIO compatibility
AWS_ACCESS_KEY_ID = MINIO_ACCESS_KEY
AWS_SECRET_ACCESS_KEY = MINIO_SECRET_KEY
AWS_S3_ENDPOINT_URL = f"http{'s' if MINIO_USE_HTTPS else ''}://{MINIO_ENDPOINT}"
AWS_STORAGE_BUCKET_NAME = MINIO_BUCKET_NAME
AWS_S3_REGION_NAME = 'us-east-1'  # MinIO default
AWS_S3_USE_SSL = MINIO_USE_HTTPS
AWS_S3_VERIFY = False  # Disable SSL verification for local development
AWS_S3_FORCE_PATH_STYLE = True  # Required for MinIO
AWS_DEFAULT_ACL = 'public-read'  # Make uploaded files publicly accessible
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# MeiliSearch Configuration
MEILISEARCH_URL = config('MEILISEARCH_URL', default='http://localhost:7700')
MEILISEARCH_MASTER_KEY = config('MEILISEARCH_MASTER_KEY', default='itqan-meili-master-key-dev')
MEILISEARCH_TIMEOUT = config('MEILISEARCH_TIMEOUT', default=30, cast=int)

# MeiliSearch Index Configuration
MEILISEARCH_INDEXES = {
    'resources': {
        'primary_key': 'id',
        'searchable_attributes': [
            'title',
            'title_ar',
            'description', 
            'description_ar',
            'content',
            'content_ar',
            'tags'
        ],
        'filterable_attributes': [
            'resource_type',
            'language',
            'status',
            'created_by',
            'license_type',
            'is_public'
        ],
        'sortable_attributes': [
            'created_at',
            'updated_at',
            'title',
            'title_ar'
        ],
        'ranking_rules': [
            'words',
            'typo',
            'proximity',
            'attribute',
            'sort',
            'exactness'
        ]
    },
    'users': {
        'primary_key': 'id',
        'searchable_attributes': [
            'first_name',
            'last_name',
            'email',
            'organization'
        ],
        'filterable_attributes': [
            'role',
            'is_active',
            'email_verified'
        ],
        'sortable_attributes': [
            'created_at',
            'last_login',
            'first_name',
            'last_name'
        ]
    },
    'media': {
        'primary_key': 'id',
        'searchable_attributes': [
            'title',
            'description',
            'original_filename',
            'tags'
        ],
        'filterable_attributes': [
            'media_type',
            'uploaded_by',
            'folder'
        ],
        'sortable_attributes': [
            'created_at',
            'file_size',
            'title'
        ]
    }
}

# Authentication backends - Use ModelBackend only since we have custom User model with email field
# Our custom User model (apps.accounts.models.User) has its own email field and email_verified field
# We don't need allauth's account_emailaddress table since we store everything in our User model
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'apps.api_keys.authentication.APIKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.api_keys.authentication.APIKeyThrottle',
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'api_key': '1000/hour',  # Default rate, overridden by individual key settings
    },
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
    'VERSION_PARAM': 'version',
}

# Simple JWT Configuration
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': 'itqan-cms',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

# DRF Spectacular Configuration (API Documentation)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Itqan CMS API',
    'DESCRIPTION': 'API for managing and distributing Quranic content, including text, audio, and translations.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/v1',
    'COMPONENT_SPLIT_REQUEST': True,
    'SORT_OPERATIONS': False,
    'TAGS': [
        {'name': 'Authentication', 'description': 'User authentication and token management'},
        {'name': 'Users', 'description': 'User account management'},
        {'name': 'Roles', 'description': 'Role-based access control'},
        {'name': 'Resources', 'description': 'Quranic content resources'},
        {'name': 'Licenses', 'description': 'Content licensing and terms'},
        {'name': 'Distributions', 'description': 'Content access formats'},
        {'name': 'Access Requests', 'description': 'Developer access approval workflow'},
        {'name': 'Usage Events', 'description': 'Analytics and usage tracking'},
    ],
}

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)

# MeiliSearch Configuration
MEILISEARCH_URL = config('MEILISEARCH_URL', default='http://localhost:7700')
MEILISEARCH_MASTER_KEY = config('MEILISEARCH_MASTER_KEY', default='masterKey')
MEILISEARCH_TIMEOUT = config('MEILISEARCH_TIMEOUT', default=30, cast=int)
MEILISEARCH_INDEXES = {
    'resources': {
        'uid': 'resources',
        'primary_key': 'id',
        'searchable_attributes': ['title', 'description', 'language'],
        'filterable_attributes': ['resource_type', 'language', 'publisher_id', 'is_active'],
        'sortable_attributes': ['created_at', 'updated_at', 'published_at'],
        'ranking_rules': [
            'words',
            'typo',
            'proximity',
            'attribute',
            'sort',
            'exactness',
            'published_at:desc'
        ]
    }
}

# Site ID (required for allauth)
SITE_ID = 1

# Django Allauth Configuration
# NOTE: We primarily use our custom User model with built-in email management
# Allauth is only used for OAuth (Google/GitHub) authentication, not email verification
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none'  # We handle email verification in our custom User model
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'  # Points to our custom User.email field
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False  # We manage email verification manually
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_ADAPTER = 'apps.accounts.adapters.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'apps.accounts.adapters.SocialAccountAdapter'

# Social account configuration - for OAuth only (Google/GitHub)
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # We handle email verification in User model
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_QUERY_EMAIL = True

# NOTE: We use our custom User model with built-in email field and email_verified field
# No need for allauth's account_emailaddress table since email data is stored in User model

# OAuth provider settings (will be configured with environment variables)
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

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
    }
}

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_CACHE_ALIAS = 'default'

# Security Settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Disable django-allauth migrations since we use our own user/email tables
MIGRATION_MODULES = {
    'account': None,
    'socialaccount': None,
}

# Additional allauth settings to prevent email table creation
ACCOUNT_EMAIL_CONFIRMATION_HMAC = False  # Disable HMAC-based confirmations
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1  # Short expiry since we don't use it