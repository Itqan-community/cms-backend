from django.db import models


class NinjaTag(models.TextChoices):
    USERS = "Users"
    ASSETS = "Assets"
    PUBLISHERS = "Publishers"
    RESOURCES = "Resources"
    AUTH = "Authentication"
    SOCIAL_AUTH = "Social Authentication"

