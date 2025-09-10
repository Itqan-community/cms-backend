from django.db import models


class NinjaTag(models.TextChoices):
    USERS = "Users"
    COURSES = "Courses"
