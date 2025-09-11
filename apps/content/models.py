from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.file_uploaders import upload_asset_files
from apps.core.file_uploaders import upload_asset_thumbnails
from apps.core.file_uploaders import upload_organization_covers
from apps.core.file_uploaders import upload_publisher_icon
from apps.core.file_uploaders import upload_resource_files
from apps.core.models import ActiveObjectsManager
from apps.core.models import AllObjectsManager
from apps.core.models import BaseModel


class Publisher(BaseModel):
    name = models.CharField(max_length=255, help_text="Organization name e.g. 'Tafsir Center'")

    slug = models.SlugField(unique=True, help_text="URL-friendly slug e.g. 'tafsir-center'")

    icon = models.ImageField(
        upload_to=upload_publisher_icon,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg"])],
        help_text="Icon/logo image - used in V1 UI: Publisher Page",
    )

    summary = models.TextField(blank=True, help_text="Organization summary - used in V1 UI: Publisher Page")

    description = models.TextField(blank=True, help_text="Detailed organization description")

    cover_url = models.ImageField(
        upload_to=upload_organization_covers,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        help_text="Cover image for organization",
    )

    location = models.CharField(max_length=255, blank=True, help_text="Organization location")

    website = models.URLField(blank=True, help_text="Organization website")

    verified = models.BooleanField(default=False, help_text="Whether organization is verified")

    social_links = models.JSONField(default=dict, help_text="Social media links as JSON", blank=True)

    contact_email = models.EmailField(blank=True, help_text="Contact email for the organization")

    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="PublisherMember", related_name="publishers")

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"Publisher(name={self.name})"


class PublisherMember(BaseModel):  # TODO Think it
    """
    Junction table for User <-> Publisher relationships.
    Defines membership roles within organizations.
    """

    class RoleChoice(models.TextChoices):
        OWNER = "owner", _("Owner")
        MANAGER = "manager", _("Manager")

    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="publisher_memberships")
    role = models.CharField(
        max_length=20,
        choices=RoleChoice.choices,
        help_text="Member's role in the organization, just for information. This field WILL NOT be used for permission checks. or any code checks",
    )

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = ["publisher", "user"]

    def __str__(self):
        return f"PublisherMember(email={self.user.email} publisher={self.publisher.name} role={self.role})"


class License(BaseModel):
    code = models.CharField(max_length=50, unique=True, help_text="License code e.g. 'cc0', 'cc-by-4.0'")

    name = models.CharField(max_length=255, help_text="Full license name")

    short_name = models.CharField(max_length=50, blank=True, help_text="Abbreviated name")

    summary = models.TextField(blank=True, help_text="Brief license description")

    full_text = models.TextField(blank=True, help_text="Complete license text")

    is_default = models.BooleanField(default=False, help_text="Whether this is the default license")

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"License(name={self.name} code={self.code})"


class Resource(BaseModel):
    class CategoryChoice(models.TextChoices):
        RECITATION = "recitation", _("Recitation")
        MUSHAF = "mushaf", _("Mushaf")
        TAFSIR = "tafsir", _("Tafsir")

    class StatusChoice(models.TextChoices):
        DRAFT = "draft", _("Draft")
        READY = "ready", _("Ready")

    publisher = models.ForeignKey(Publisher, on_delete=models.PROTECT, related_name="resources")

    name = models.CharField(max_length=255, help_text="Resource name e.g. 'Tafsir Ibn Katheer CSV'")

    slug = models.SlugField(help_text="URL slug e.g. 'tafsir-ibn-katheer-csv'", db_index=True)

    description = models.TextField(help_text="Resource description")

    category = models.CharField(max_length=20, choices=CategoryChoice.choices, help_text="Simple options in V1")

    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.DRAFT,
        help_text="V1: ready = ready to extract Assets from",
    )

    default_license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        related_name="default_for_resources",
        help_text="Default license for this resource",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"Resource(name={self.name} category={self.category})"

    def save(self, *args, **kwargs):
        self.slug = slugify(f"{self.name}({self.publisher.slug})")
        super().save(*args, **kwargs)


class ResourceVersion(BaseModel):
    class FileTypeChoice(models.TextChoices):
        CSV = "csv", _("CSV")
        EXCEL = "excel", _("Excel")
        JSON = "json", _("JSON")
        ZIP = "zip", _("ZIP")

    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="versions")

    name = models.CharField(
        max_length=255, help_text="Version name - V1: same as resource name, V2: updates on content"
    )

    summary = models.TextField(blank=True, help_text="Version summary")

    semvar = models.CharField(
        max_length=20, help_text="Semantic versioning e.g. '1.0.0' - core to bind with an AssetVersion"
    )

    storage_url = models.FileField(
        upload_to=upload_resource_files,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "doc", "docx", "txt", "zip", "tar", "gz", "json", "xml", "csv"],
            ),
        ],
        help_text="File storage for resource version",
    )

    file_type = models.CharField(max_length=20, choices=FileTypeChoice.choices, help_text="File type")

    size_bytes = models.PositiveBigIntegerField(default=0, help_text="File size in bytes")

    is_latest = models.BooleanField(default=False, help_text="Whether this is the latest version")

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        verbose_name = "Resource Version"
        verbose_name_plural = "Resource Versions"
        unique_together = ["resource", "semvar"]

    def __str__(self):
        return f"ResourceVersion(resource={self.resource.name} semvar={self.semvar})"

    def save(self, *args, **kwargs):
        # Auto-compute human_readable_size from storage file when available and not set
        if (not self.size_bytes or self.size_bytes == 0) and self.storage_url:
            try:
                # FileField provides size when the file is available
                self.size_bytes = self.storage_url.size or 0
            except Exception:
                # If storage backend cannot determine size, leave as 0
                pass
        if self.is_latest:
            # Set all other versions of this resource to is_latest=False
            ResourceVersion.objects.filter(
                resource=self.resource,
                is_latest=True,
            ).exclude(pk=self.pk).update(is_latest=False)

        super().save(*args, **kwargs)


class Asset(BaseModel):
    class AssetChoice(models.TextChoices):
        RECITATION = "recitation", _("Recitation")
        MUSHAF = "mushaf", _("Mushaf")
        TAFSIR = "tafsir", _("Tafsir")

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="assets")

    name = models.CharField(max_length=255, help_text="Asset name")

    description = models.TextField(help_text="Asset description")

    long_description = models.TextField(blank=True, help_text="Extended description")

    thumbnail_url = models.ImageField(
        upload_to=upload_asset_thumbnails,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        help_text="Asset thumbnail image",
    )

    category = models.CharField(
        max_length=20, choices=AssetChoice.choices, help_text="Asset category matching resource categories"
    )

    license = models.ForeignKey(License, on_delete=models.PROTECT, related_name="assets")

    file_size = models.CharField(max_length=50, help_text="Human readable file size e.g. '2.5 MB'")

    format = models.CharField(max_length=50, help_text="File format")

    encoding = models.CharField(max_length=50, default="UTF-8", help_text="Text encoding")

    version = models.CharField(max_length=50, help_text="Asset version")

    language = models.CharField(max_length=10, help_text="Asset language code")

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"Asset(title={self.title} category={self.category})"

    @staticmethod
    def _parse_file_size_to_bytes(file_size_str):
        """Convert human readable file size to bytes"""
        if not file_size_str:
            return 0

        import re

        # Extract number and unit from string like "2.5 MB"
        match = re.match(r"([0-9.]+)\s*([KMGTPE]?B)", file_size_str.upper())
        if not match:
            return 0

        size, unit = match.groups()
        size = float(size)

        units = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
            "PB": 1024**5,
            "EB": 1024**6,
        }

        return int(size * units.get(unit, 1))

    def get_related_assets(self, limit=5):
        """Get related assets from same category and publisher"""
        return Asset.objects.filter(
            category=self.category,
            resource__publishing_organization=self.resource.publisher,
            is_active=True,
        ).exclude(id=self.id)[:limit]

    @property
    def human_readable_size(self):
        """Get file size in bytes (computed from human readable)"""
        return self._parse_file_size_to_bytes(self.file_size)


class AssetVersion(BaseModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="versions")

    resource_version = models.ForeignKey(ResourceVersion, on_delete=models.CASCADE, related_name="asset_versions")

    name = models.CharField(max_length=255, help_text="Asset version name")

    summary = models.TextField(blank=True, help_text="Asset version summary")

    file_url = models.FileField(
        upload_to=upload_asset_files,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "doc", "docx", "txt", "zip", "tar", "gz", "json", "xml", "csv"],
            ),
        ],
        help_text="Direct file for asset",
    )

    size_bytes = models.PositiveBigIntegerField(help_text="File size in bytes")

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        verbose_name = "Asset Version"
        verbose_name_plural = "Asset Versions"

    def __str__(self):
        return f"AssetVersion(asset={self.asset.name} version={self.resource_version.semvar})"

    @property
    def human_readable_size(self):
        """Convert bytes to human readable format"""
        if self.size_bytes == 0:
            return "0 B"

        import math

        size = self.size_bytes
        units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]

        if size == 0:
            return "0 B"

        i = math.floor(math.log(size, 1024))
        p = math.pow(1024, i)
        s = round(size / p, 2)

        return f"{s} {units[i]}"


class AssetAccessRequest(BaseModel):
    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    class IntendedUseChoice(models.TextChoices):
        COMMERCIAL = "commercial", _("Commercial")
        NON_COMMERCIAL = "non-commercial", _("Non-Commercial")

    developer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="asset_requests"
    )

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="access_requests")

    status = models.CharField(max_length=20, choices=StatusChoice.choices, default=StatusChoice.PENDING)

    developer_access_reason = models.TextField(help_text="Reason for requesting access - used in V1 UI")

    intended_use = models.CharField(
        max_length=20, choices=IntendedUseChoice.choices, help_text="Commercial or non-commercial use"
    )

    admin_response = models.TextField(blank=True, help_text="Admin response message")

    approved_at = models.DateTimeField(null=True, blank=True, help_text="When request was approved")

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_requests",
    )

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        verbose_name = "Asset Access Request"
        verbose_name_plural = "Asset Access Requests"
        unique_together = ["developer_user", "asset"]

    def __str__(self):
        return f"{self.developer_user.email} -> {self.asset.name} ({self.status})"
