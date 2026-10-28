"""
Itqan CMS - Test Settings
"""

from .development import *  # noqa: F401, F403

# =========================
# Password hashing
# =========================
# The default PBKDF2 hasher runs ~1M iterations per hash, which made every
# test that creates a user with a password spend ~0.5s in setUp.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
