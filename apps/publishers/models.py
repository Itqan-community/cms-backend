from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel
from apps.core.slugs import slugify_name
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

    mixpanel_board_url = models.URLField(
        blank=True, null=True, help_text="Public Mixpanel board URL for this publisher's analytics dashboard"
    )

    is_verified = models.BooleanField(default=True, help_text="Whether publisher is verified")

    contact_email = models.EmailField(blank=True, help_text="Contact email for the publisher")

    foundation_year = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Year the publisher was established"
    )

    country = models.CharField(max_length=100, blank=True, help_text="Country of the publisher")

    members = models.ManyToManyField(User, through="PublisherMember", related_name="publishers")

    def __str__(self):
        return f"Publisher(name={self.name})"

    def save(self, *args, **kwargs):
        self.slug = slugify_name(self.name_en, self.name_ar)
        super().save(*args, **kwargs)


class PublisherMember(BaseModel):
    """
    Junction table for User <-> Publisher relationships.
    A user may belong to more than one publisher (many-to-many).
    """

    class RoleChoice(models.TextChoices):
        ADMIN = "admin", _("Admin")
        STAFF = "staff", _("Staff")

    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACTIVE = "active", _("Active")

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="publisher_memberships")
    role = models.CharField(
        max_length=20,
        choices=RoleChoice.choices,
        help_text="Role label for this member. Drives permission group assignment on activation; has no effect on runtime authorization.",
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.PENDING,
        help_text="PENDING until the member accepts their invitation; ACTIVE after acceptance.",
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


class PublisherMemberInvitation(BaseModel):
    """
    A pending invitation for a user to become a member of a publisher.
    Carries a single-use hashed token and audit trail.
    """

    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        ACCEPTED = "accepted", _("Accepted")
        EXPIRED = "expired", _("Expired")
        CANCELLED = "cancelled", _("Cancelled")

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="member_invitations")
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_member_invitations"
    )
    member = models.ForeignKey(
        PublisherMember, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations"
    )
    status = models.CharField(max_length=20, choices=StatusChoice.choices, default=StatusChoice.PENDING)
    token_hash = models.CharField(
        max_length=64, unique=True, help_text="sha256 of the raw token; raw token only in email."
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="cancelled_member_invitations"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["member"],
                condition=models.Q(status="pending"),
                name="uniq_pending_invite_per_member",
            ),
        ]
        indexes = [models.Index(fields=["token_hash"])]

    @property
    def email(self) -> str | None:
        """Derived from member's user. None if member was deleted (cancelled invitation audit trail)."""
        return self.member.user.email if self.member_id else None

    @property
    def role(self) -> str | None:
        """Derived from member. None if member was deleted (cancelled invitation audit trail)."""
        return self.member.role if self.member_id else None

    def __str__(self):
        return f"PublisherMemberInvitation(member={self.member_id} publisher={self.publisher_id} status={self.status})"
