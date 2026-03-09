from django.db import models


class NinjaTag(models.TextChoices):
    """Used for tagging API endpoints in django-ninja"""

    USERS = "Users"
    ASSETS = "Assets"
    PUBLISHERS = "Publishers"
    RESOURCES = "Resources"
    AUTH = "Authentication"
    SOCIAL_AUTH = "Social Authentication"
    RECITATIONS = "Recitations"
    RECITERS = "Reciters"
    RIWAYAHS = "Riwayahs"
    QIRAAHS = "Qiraahs"
    ISSUE_REPORTS = "Issue Reports"
    FAVORITES = "Favorites"
    BOOKMARKS = "Bookmarks"
    LISTENING_HISTORY = "Listening History"
    PREFERENCES = "Preferences"
