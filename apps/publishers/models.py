from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.core.uploads import upload_to_publisher_icons
from apps.users.models import User


class Publisher(BaseModel):
    name = models.CharField(max_length=255, help_text="Publisher name e.g. 'Tafsir Center'")

    slug = models.SlugField(unique=True, allow_unicode=True, help_text="URL-friendly slug e.g. 'tafsir-center'")

    icon_url = models.ImageField(
        upload_to=upload_to_publisher_icons,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg"])],
        help_text="Icon/logo image - used in V1 UI: Publisher Page",
    )

    description = models.TextField(blank=True, help_text="Detailed publisher description")

    address = models.CharField(max_length=255, blank=True, help_text="Publisher address")

    website = models.URLField(blank=True, help_text="Publisher website")

    is_verified = models.BooleanField(default=True, help_text="Whether publisher is verified")

    contact_email = models.EmailField(blank=True, help_text="Contact email for the publisher")

    members = models.ManyToManyField(User, through="PublisherMember", related_name="publishers")

    def __str__(self):
        return f"Publisher(name={self.name})"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name[:50], allow_unicode=True)
        super().save(*args, **kwargs)


class PublisherMember(BaseModel):
    """
    Junction table for User <-> Publisher relationships.
    Defines membership roles within publishers.
    """

    class RoleChoice(models.TextChoices):
        OWNER = "owner", _("Owner")
        MANAGER = "manager", _("Manager")

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="publisher_memberships")
    role = models.CharField(
        max_length=20,
        choices=RoleChoice.choices,
        help_text="Member's role in the publisher, just for information. This field WILL NOT be used for permission checks. or any code checks",
    )

    class Meta:
        unique_together = ["publisher", "user"]

    def __str__(self):
        return f"PublisherMember(email={self.user.email} publisher={self.publisher_id} role={self.role})"


class Domain(BaseModel):
    domain = models.CharField(max_length=100, unique=True, help_text="www.domain.com")
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="domains")
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Domain(domain={self.domain} publisher={self.publisher_id})"

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Get all other primary domains with the same tenant
        domain_list = Domain.objects.filter(publisher=self.publisher, is_primary=True).exclude(pk=self.pk)
        # If we have no primary domain yet, set as primary domain by default
        self.is_primary = self.is_primary or (not domain_list.exists())
        if self.is_primary:
            # Remove primary status of existing domains for tenant
            domain_list.update(is_primary=False)
        super().save(*args, **kwargs)
