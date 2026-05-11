from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField, EmailField
from django.utils.translation import gettext_lazy as _
from ninja_keys.models import AbstractAPIKey, APIKeyManager as BaseAPIKeyManager
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
        return f"{self.name}"

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)


class APIKeyManager(BaseAPIKeyManager):
    pass


class APIKey(AbstractAPIKey):
    objects: ClassVar[APIKeyManager] = APIKeyManager()

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name=_("User"),
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="uniq_user_api_key_name"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.user_id})"


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
        default=False, help_text="Whether the user has completed their profile setup"
    )

    def __str__(self):
        return f"Developer(user={self.user_id})"

    def save(self, *args, **kwargs):
        # Compute completion: all key fields must be non-empty
        fields_filled = all(
            [
                bool((self.bio or "").strip()),
                bool((self.project_summary or "").strip()),
                bool((self.project_url or "").strip()),
                bool((self.job_title or "").strip()),
            ]
        )
        self.profile_completed = fields_filled
        super().save(*args, **kwargs)
