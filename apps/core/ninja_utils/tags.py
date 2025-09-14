from django.db import models


class NinjaTag(models.TextChoices):
    USERS = "Users"
    ASSETS = "Assets"
    LICENSES = "Licenses"
    PUBLISHERS = "Publishers"
