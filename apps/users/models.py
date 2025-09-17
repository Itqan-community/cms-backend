from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField
from django.db.models import EmailField
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from apps.core.models import BaseModel

from .managers import UserManager


class User(BaseModel, AbstractUser):
    # The First and last name do not cover name patterns around the globe
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    username = None  # type: ignore[assignment]
    date_joined = None  # type: ignore[assignment]
    name = CharField(_("Name of User"), blank=True, max_length=255)
    email = EmailField(_("email address"), db_index=True, unique=True)
    phone = PhoneNumberField(_("Phone Number"), blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def __str__(self):
        return f"User(email={self.email} name={self.name})"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)



class Developer(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="developer_profile")
    bio = models.TextField(_("Bio"), blank=True, help_text="Tell us more about you and your team")
    project_summary = models.TextField(_("Project Summary"), blank=True, help_text="Tell us about your project")
    project_url = models.URLField(
        _("Project URL"),
        blank=True,
        help_text="Link to the user's project (e.g., GitHub repository, personal website)",
    )
    job_title = models.CharField(_("Job Title"), max_length=255, blank=True)
    profile_completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed their profile setup"
    )

    def __str__(self):
        return f"Developer(user={self.user_id})"