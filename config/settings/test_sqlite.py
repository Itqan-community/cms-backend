"""
Minimal test settings using SQLite — no PostgreSQL or secrets required.
Used only for running the TDD test suite in CI-constrained environments.
"""

import os

# Disable feature flags that require secrets before importing base
os.environ.setdefault("ENABLE_ALLAUTH", "false")
os.environ.setdefault("ENABLE_OAUTH2", "false")
os.environ.setdefault("SAML_IDP_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "true")

from .development import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
