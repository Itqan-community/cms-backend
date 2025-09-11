from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField
from django.db.models import EmailField
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    # The First and last name do not cover name patterns around the globe
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    username = None  # type: ignore[assignment]
    name = CharField(_("Name of User"), blank=True, max_length=255)
    email = EmailField(_("email address"), db_index=True, unique=True)

    # profile:
    bio = models.TextField(_("Bio"), blank=True)
    work_summary = models.TextField(_("Work Summary"), blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    # class Meta:
    #     constraints = [
    #         # unique together
    #         models.UniqueConstraint()
    #     ]

    def __str__(self):
        return f"User(email={self.email} name={self.name})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)
