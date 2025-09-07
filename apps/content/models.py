"""
Complete ERD-aligned models for Itqan CMS
Based on db_design_v1.drawio specification
"""

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.core.validators import URLValidator
from django.db import models

from apps.core.models import ActiveObjectsManager
from apps.core.models import AllObjectsManager
from apps.core.models import BaseModel
from apps.core.utils import upload_to_asset_files
from apps.core.utils import upload_to_asset_thumbnails
from apps.core.utils import upload_to_license_icons
from apps.core.utils import upload_to_organization_covers
from apps.core.utils import upload_to_organization_icons
from apps.core.utils import upload_to_resource_files


# ============================================================================
# 1. PUBLISHING ORGANIZATION
# ============================================================================
class PublishingOrganization(BaseModel):
    """
    Publishing organization entity from ERD.
    Organizations that publish resources and have multiple members.
    """

    # Core fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Organization name e.g. 'Tafsir Center'",
    )

    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly slug e.g. 'tafsir-center'",
    )

    icone_image_url = models.ImageField(
        upload_to=upload_to_organization_icons,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg"],
            ),
        ],
        help_text="Icon/logo image - used in V1 UI: Publisher Page",
    )

    summary = models.TextField(
        blank=True,
        help_text="Organization summary - used in V1 UI: Publisher Page",
    )

    # Additional fields for API support
    description = models.TextField(
        blank=True,
        help_text="Detailed organization description",
    )

    bio = models.TextField(
        blank=True,
        help_text="Organization bio for API responses",
    )

    cover_url = models.ImageField(
        upload_to=upload_to_organization_covers,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"],
            ),
        ],
        help_text="Cover image for organization",
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Organization location",
    )

    website = models.URLField(
        blank=True,
        help_text="Organization website",
    )

    verified = models.BooleanField(
        default=False,
        help_text="Whether organization is verified",
    )

    social_links = models.JSONField(
        default=dict,
        help_text="Social media links as JSON",
    )

    # Additional fields for API compatibility
    contact_email = models.EmailField(
        blank=True,
        help_text="Contact email for the organization",
    )

    # Relationships
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="PublishingOrganizationMember",
        related_name="publishing_organizations",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "publishing_organization"
        verbose_name = "Publishing Organization"
        verbose_name_plural = "Publishing Organizations"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ============================================================================
# 2. PUBLISHING ORGANIZATION MEMBER
# ============================================================================
class PublishingOrganizationMember(BaseModel):
    """
    Junction table for User <-> PublishingOrganization relationships.
    Defines membership roles within organizations.
    """

    ROLE_CHOICES = [
        ("owner", "Owner"),
        (
            "manager",
            "Manager",
        ),  # V1: Itqan team to upload data on publishers behalf from Admin Panel. V2: more rules.
    ]

    # Foreign keys from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )

    # Role field from ERD
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        help_text="Member's role in the organization",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "publishing_organization_member"
        unique_together = ["publishing_organization", "user"]
        verbose_name = "Organization Member"
        verbose_name_plural = "Organization Members"

    def __str__(self):
        return f"{self.user.email} -> {self.publishing_organization.name} ({self.role})"


# ============================================================================
# 3. LICENSE
# ============================================================================
class License(BaseModel):
    """
    License definitions with terms and permissions.
    Each resource has a default license.
    """

    # Core fields that would be in detailed license schema
    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="License code e.g. 'cc0', 'cc-by-4.0'",
    )

    name = models.CharField(
        max_length=255,
        help_text="Full license name",
    )

    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Abbreviated name",
    )

    url = models.URLField(
        blank=True,
        help_text="Official license URL",
    )

    icon_url = models.ImageField(
        upload_to=upload_to_license_icons,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp", "svg"],
            ),
        ],
        help_text="License icon image",
    )

    summary = models.TextField(
        blank=True,
        help_text="Brief license description",
    )

    full_text = models.TextField(
        blank=True,
        help_text="Complete license text",
    )

    legal_code_url = models.URLField(
        blank=True,
        help_text="Legal code URL",
    )

    # JSON fields for structured data
    license_terms = models.JSONField(
        default=list,
        help_text="License terms as JSON array",
    )

    permissions = models.JSONField(
        default=list,
        help_text="Permissions as JSON array",
    )

    conditions = models.JSONField(
        default=list,
        help_text="Conditions as JSON array",
    )

    limitations = models.JSONField(
        default=list,
        help_text="Limitations as JSON array",
    )

    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default license",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "license"
        verbose_name = "License"
        verbose_name_plural = "Licenses"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


# ============================================================================
# 4. RESOURCE
# ============================================================================
class Resource(BaseModel):
    """
    Core resource entity from ERD.
    Original content packages published by organizations.
    """

    CATEGORY_CHOICES = [
        ("recitation", "Recitation"),
        ("mushaf", "Mushaf"),
        ("tafsir", "Tafsir"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("ready", "Ready"),  # V1: ready = ready to extract Assets from
    ]

    # Core fields from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.PROTECT,
        related_name="resources",
    )

    name = models.CharField(
        max_length=255,
        help_text="Resource name e.g. 'Tafsir Ibn Katheer CSV'",
    )

    slug = models.SlugField(
        help_text="URL slug e.g. 'tafsir-ibn-katheer-csv'",
    )

    description = models.TextField(
        help_text="Resource description",
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Simple options in V1",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
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

    class Meta:
        db_table = "resource"
        verbose_name = "Resource"
        verbose_name_plural = "Resources"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publishing_organization"]),
            models.Index(fields=["category"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.category})"

    def get_latest_version(self):
        """Get the latest version of this resource"""
        return self.versions.filter(is_latest=True).first()

    def get_all_versions(self):
        """Get all versions ordered by semantic version"""
        return self.versions.all().order_by("-created_at")

    def create_version(
        self,
        semvar,
        storage_url,
        file_type,
        size_bytes,
        name=None,
        summary="",
        set_as_latest=True,
    ):
        """Create a new version for this resource"""
        return ResourceVersion.create_new_version(
            resource=self,
            semvar=semvar,
            storage_url=storage_url,
            type=file_type,
            size_bytes=size_bytes,
            name=name or self.name,
            summary=summary,
            set_as_latest=set_as_latest,
        )

    @property
    def latest_version(self):
        """Property to get the latest version"""
        return self.get_latest_version()

    @property
    def version_count(self):
        """Get the number of versions for this resource"""
        return self.versions.count()


# ============================================================================
# 5. RESOURCE VERSION
# ============================================================================
class ResourceVersion(BaseModel):
    """
    Versioned instances of resources with semantic versioning.
    Links to storage URLs and file metadata.
    """

    TYPE_CHOICES = [
        ("csv", "CSV"),
        ("excel", "Excel"),
        ("json", "JSON"),
        ("zip", "ZIP"),
    ]

    # Relationships
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    # Version fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Version name - V1: same as resource name, V2: updates on content",
    )

    summary = models.TextField(
        blank=True,
        help_text="Version summary",
    )

    semvar = models.CharField(
        max_length=20,
        help_text="Semantic versioning e.g. '1.0.0' - core to bind with an AssetVersion",
    )

    storage_url = models.FileField(
        upload_to=upload_to_resource_files,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "txt",
                    "zip",
                    "tar",
                    "gz",
                    "json",
                    "xml",
                    "csv",
                ],
            ),
        ],
        help_text="File storage for resource version",
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        help_text="File type",
    )

    size_bytes = models.PositiveBigIntegerField(
        help_text="File size in bytes",
    )

    is_latest = models.BooleanField(
        default=False,
        help_text="Whether this is the latest version",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "resource_version"
        verbose_name = "Resource Version"
        verbose_name_plural = "Resource Versions"
        ordering = ["-created_at"]
        unique_together = ["resource", "semvar"]

    def __str__(self):
        return f"{self.resource.name} v{self.semvar}"

    def save(self, *args, **kwargs):
        """
        Override save to implement is_latest constraint.
        Only one version per resource can be is_latest=True.
        """
        if self.is_latest:
            # Set all other versions of this resource to is_latest=False
            ResourceVersion.objects.filter(
                resource=self.resource,
                is_latest=True,
            ).exclude(pk=self.pk).update(is_latest=False)

        super().save(*args, **kwargs)

    @classmethod
    def create_new_version(
        cls,
        resource,
        semvar,
        storage_url,
        asset_type,
        size_bytes,
        name=None,
        summary="",
        set_as_latest=True,
    ):
        """
        Create a new version of a resource with proper version management.
        """
        if name is None:
            name = resource.name

        version = cls.objects.create(
            resource=resource,
            name=name,
            summary=summary,
            semvar=semvar,
            storage_url=storage_url,
            type=type,
            size_bytes=size_bytes,
            is_latest=set_as_latest,
        )

        return version

    @property
    def version_number(self):
        """Get version number tuple for comparison"""
        try:
            parts = self.semvar.split(".")
            return tuple(int(part) for part in parts)
        except (ValueError, AttributeError):
            return (0, 0, 0)

    def is_newer_than(self, other_version):
        """Check if this version is newer than another version"""
        return self.version_number > other_version.version_number


# ============================================================================
# 6. ASSET
# ============================================================================
class Asset(BaseModel):
    """
    Individual assets that can be downloaded.
    Part of resources, published by organizations.
    """

    # Relationships from ERD
    publishing_organization = models.ForeignKey(
        PublishingOrganization,
        on_delete=models.PROTECT,
        related_name="assets",
    )

    # Core asset fields that would be in the detailed schema
    name = models.CharField(
        max_length=255,
        help_text="Asset name",
    )

    title = models.CharField(
        max_length=255,
        help_text="Display title for API",
    )

    description = models.TextField(
        help_text="Asset description",
    )

    long_description = models.TextField(
        blank=True,
        help_text="Extended description",
    )

    thumbnail_url = models.ImageField(
        upload_to=upload_to_asset_thumbnails,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"],
            ),
        ],
        help_text="Asset thumbnail image",
    )

    category = models.CharField(
        max_length=20,
        choices=Resource.CATEGORY_CHOICES,
        help_text="Asset category matching resource categories",
    )

    # License relationship
    license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        related_name="assets",
    )

    # Technical details
    file_size = models.CharField(
        max_length=50,
        help_text="Human readable file size e.g. '2.5 MB'",
    )

    format = models.CharField(
        max_length=50,
        help_text="File format",
    )

    encoding = models.CharField(
        max_length=50,
        default="UTF-8",
        help_text="Text encoding",
    )

    version = models.CharField(
        max_length=50,
        help_text="Asset version",
    )

    language = models.CharField(
        max_length=10,
        help_text="Asset language code",
    )

    # Stats
    download_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of downloads",
    )

    view_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of views",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "asset"
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["publishing_organization"]),
            models.Index(fields=["category"]),
            models.Index(fields=["license"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.category})"

    @classmethod
    def create_from_resource_version(cls, resource_version, asset_data):
        """
        Create an asset extracted from a resource version.
        Inherits publisher and category from resource.
        """
        resource = resource_version.resource

        # Extract AssetVersion-specific data
        file_url = asset_data.pop("file_url", "")
        version_summary = asset_data.pop(
            "version_summary",
            f"Extracted from {resource_version}",
        )

        # Set defaults from resource if not provided
        asset_data.setdefault(
            "publishing_organization",
            resource.publishing_organization,
        )
        asset_data.setdefault("license", resource.default_license)
        asset_data.setdefault("category", resource.category)

        # Create the asset
        asset = cls.objects.create(**asset_data)

        # Create the asset version linking to resource version
        AssetVersion.objects.create(
            asset=asset,
            resource_version=resource_version,
            name=asset.title,
            summary=version_summary,
            file_url=file_url,
            size_bytes=cls._parse_file_size_to_bytes(asset.file_size),
        )

        return asset

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

    def get_latest_version(self):
        """Get the most recent version of this asset"""
        return self.versions.order_by("-created_at").first()

    def get_related_assets(self, limit=5):
        """Get related assets from same category and publisher"""
        return Asset.objects.filter(
            category=self.category,
            publishing_organization=self.publishing_organization,
            is_active=True,
        ).exclude(id=self.id)[:limit]

    def increment_download_count(self):
        """Increment download counter with async processing"""
        try:
            from .tasks import update_asset_stats_async

            # Try async update first
            if update_asset_stats_async(self.id, "download_count"):
                # Optimistically update local instance without DB hit
                self.download_count += 1
                return
        except ImportError:
            pass

        # Fallback to synchronous atomic update
        from django.db.models import F

        Asset.objects.filter(id=self.id).update(download_count=F("download_count") + 1)
        self.refresh_from_db(fields=["download_count"])

    def increment_view_count(self):
        """Increment view counter with async processing"""
        try:
            from .tasks import update_asset_stats_async

            # Try async update first
            if update_asset_stats_async(self.id, "view_count"):
                # Optimistically update local instance without DB hit
                self.view_count += 1
                return
        except ImportError:
            pass

        # Fallback to synchronous atomic update
        from django.db.models import F

        Asset.objects.filter(id=self.id).update(view_count=F("view_count") + 1)
        self.refresh_from_db(fields=["view_count"])

    @property
    def size_bytes(self):
        """Get file size in bytes (computed from human readable)"""
        return self._parse_file_size_to_bytes(self.file_size)

    @property
    def is_public(self):
        """Check if asset is publicly accessible (based on license)"""
        # This would be determined by license terms
        return self.license.code in ["cc0", "cc-by-4.0"] if self.license else False


# ============================================================================
# 7. ASSET VERSION
# ============================================================================
class AssetVersion(BaseModel):
    """
    Individual downloadable assets extracted from resource versions.
    """

    # Relationships
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    resource_version = models.ForeignKey(
        ResourceVersion,
        on_delete=models.CASCADE,
        related_name="asset_versions",
    )

    # Asset version fields from ERD
    name = models.CharField(
        max_length=255,
        help_text="Asset version name",
    )

    summary = models.TextField(
        blank=True,
        help_text="Asset version summary",
    )

    file_url = models.FileField(
        upload_to=upload_to_asset_files,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "pdf",
                    "doc",
                    "docx",
                    "txt",
                    "zip",
                    "tar",
                    "gz",
                    "json",
                    "xml",
                    "csv",
                ],
            ),
        ],
        help_text="Direct file for asset",
    )

    size_bytes = models.PositiveBigIntegerField(
        help_text="File size in bytes",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "asset_version"
        verbose_name = "Asset Version"
        verbose_name_plural = "Asset Versions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.asset.name} -> {self.resource_version.semvar}"

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

    def get_download_url(self):
        """Get the download URL for this asset version"""
        return self.file_url.url if self.file_url else None

    @property
    def resource_semvar(self):
        """Get the semantic version of the parent resource"""
        return self.resource_version.semvar


# ============================================================================
# 8. ASSET ACCESS REQUEST
# ============================================================================
class AssetAccessRequest(BaseModel):
    """
    User requests for asset access with approval workflow.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    INTENDED_USE_CHOICES = [
        ("commercial", "Commercial"),
        ("non-commercial", "Non-Commercial"),
    ]

    # Relationships from ERD
    developer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asset_requests",
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="access_requests",
    )

    # Request fields from ERD
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    developer_access_reason = models.TextField(
        help_text="Reason for requesting access - used in V1 UI",
    )

    intended_use = models.CharField(
        max_length=20,
        choices=INTENDED_USE_CHOICES,
        help_text="Commercial or non-commercial use",
    )

    # Admin response
    admin_response = models.TextField(
        blank=True,
        help_text="Admin response message",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was approved",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_requests",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "asset_access_request"
        verbose_name = "Asset Access Request"
        verbose_name_plural = "Asset Access Requests"
        ordering = ["-created_at"]
        unique_together = ["developer_user", "asset"]

    def __str__(self):
        return f"{self.developer_user.email} -> {self.asset.title} ({self.status})"

    def approve_request(self, approved_by_user=None, auto_approved=True):
        """
        Approve the access request and create AssetAccess.
        For V1: Auto-approval without admin intervention.
        """
        from django.utils import timezone

        if self.status != "pending":
            raise ValueError(f"Cannot approve request with status '{self.status}'")

        # Update request status
        self.status = "approved"
        self.approved_at = timezone.now()
        self.approved_by = approved_by_user

        if auto_approved:
            self.admin_response = "Automatically approved (V1 policy)"

        self.save()

        # Create AssetAccess (use all_objects to bypass is_active filter)
        access = AssetAccess.all_objects.create(
            asset_access_request=self,
            user=self.developer_user,
            asset=self.asset,
            effective_license=self.asset.license,
            download_url=self._generate_download_url(),
            expires_at=None,  # V1: No expiration
        )

        return access

    def reject_request(self, rejected_by_user=None, reason=""):
        """
        Reject the access request.
        """
        from django.utils import timezone

        if self.status != "pending":
            raise ValueError(f"Cannot reject request with status '{self.status}'")

        self.status = "rejected"
        self.approved_at = timezone.now()
        self.approved_by = rejected_by_user
        self.admin_response = reason or "Request rejected"
        self.save()

    def _generate_download_url(self):
        """
        Generate download URL for the asset.
        In V1: Direct file URL from asset version.
        """
        latest_version = self.asset.get_latest_version()
        if latest_version:
            return latest_version.file_url
        return ""

    @classmethod
    def request_access(cls, user, asset, purpose, intended_use, auto_approve=True):
        """
        Create access request and optionally auto-approve for V1.
        """
        # Check if request already exists
        existing_request = cls.objects.filter(
            developer_user=user,
            asset=asset,
        ).first()

        if existing_request:
            if existing_request.status == "approved":
                try:
                    access = existing_request.access_grant
                except AssetAccess.DoesNotExist:
                    access = None
                return existing_request, access
            if existing_request.status == "pending":
                # Re-approve if auto_approve is enabled
                if auto_approve:
                    access = existing_request.approve_request(auto_approved=True)
                    return existing_request, access
                return existing_request, None

        # Create new request
        request = cls.objects.create(
            developer_user=user,
            asset=asset,
            developer_access_reason=purpose,
            intended_use=intended_use,
        )

        # Auto-approve for V1
        access = None
        if auto_approve:
            access = request.approve_request(auto_approved=True)

        return request, access

    @property
    def is_approved(self):
        """Check if request is approved"""
        return self.status == "approved"

    @property
    def is_pending(self):
        """Check if request is pending"""
        return self.status == "pending"

    @property
    def is_rejected(self):
        """Check if request is rejected"""
        return self.status == "rejected"


# ============================================================================
# 9. ASSET ACCESS
# ============================================================================
class AssetAccess(BaseModel):
    """
    Granted access to assets for users.
    Created when access requests are approved.
    """

    # Relationships from ERD
    asset_access_request = models.OneToOneField(
        AssetAccessRequest,
        on_delete=models.CASCADE,
        related_name="access_grant",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asset_accesses",
    )

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="user_accesses",
    )

    # License snapshot from ERD
    effective_license = models.ForeignKey(
        License,
        on_delete=models.PROTECT,
        help_text="License snapshot at time of access grant",
    )

    # Access details
    granted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When access was granted",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When access expires (null = never expires)",
    )

    download_url = models.URLField(
        blank=True,
        help_text="Direct download URL",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "asset_access"
        verbose_name = "Asset Access"
        verbose_name_plural = "Asset Accesses"
        ordering = ["-granted_at"]
        unique_together = ["user", "asset"]

    def __str__(self):
        return f"{self.user.email} has access to {self.asset.title}"

    @property
    def is_active(self):
        """Check if access is currently active (not expired)"""
        if not self.expires_at:
            return True  # Never expires

        from django.utils import timezone

        return timezone.now() < self.expires_at

    @property
    def is_expired(self):
        """Check if access has expired"""
        return not self.is_active

    def get_download_url(self):
        """Get the download URL for this access"""
        if self.download_url:
            return self.download_url
        latest_version = self.asset.get_latest_version()
        return latest_version.file_url.url if latest_version and latest_version.file_url else None

    def create_usage_event(
        self,
        usage_kind="file_download",
        ip_address=None,
        user_agent="",
    ):
        """
        Create a usage event when the asset is accessed.
        """

        return UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=usage_kind,
            subject_kind="asset",
            asset_id=self.asset.id,
            metadata={
                "asset_title": self.asset.title,
                "file_size": self.asset.file_size,
                "format": self.asset.format,
                "license": self.effective_license.code,
                "access_id": self.id,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def user_has_access(cls, user, asset):
        """Check if user has active access to asset"""
        try:
            access = cls.all_objects.get(user=user, asset=asset)
            return access.is_active
        except cls.DoesNotExist:
            return False

    @classmethod
    def get_user_access(cls, user, asset):
        """Get user's access to asset if it exists"""
        try:
            return cls.all_objects.get(user=user, asset=asset)
        except cls.DoesNotExist:
            return None


# ============================================================================
# 10. USAGE EVENT
# ============================================================================
class UsageEvent(BaseModel):
    """
    Analytics tracking for asset and resource usage.
    Tracks downloads and other usage events.
    """

    USAGE_KIND_CHOICES = [
        ("file_download", "File Download"),
        ("view", "View"),
        ("api_access", "API Access"),
    ]

    SUBJECT_KIND_CHOICES = [
        ("resource", "Resource"),
        ("asset", "Asset"),
    ]

    # User tracking
    developer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_events",
    )

    # Event details from ERD
    usage_kind = models.CharField(
        max_length=20,
        choices=USAGE_KIND_CHOICES,
        help_text="Type of usage event",
    )

    subject_kind = models.CharField(
        max_length=20,
        choices=SUBJECT_KIND_CHOICES,
        help_text="Whether tracking resource or asset",
    )

    # Conditional foreign keys based on subject_kind
    resource_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Resource ID if subject_kind = 'resource'",
    )

    asset_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Asset ID if subject_kind = 'asset'",
    )

    # Event metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Additional event metadata",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="User IP address",
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User browser/client information",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "usage_event"
        verbose_name = "Usage Event"
        verbose_name_plural = "Usage Events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["developer_user"]),
            models.Index(fields=["usage_kind"]),
            models.Index(fields=["subject_kind"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.developer_user.email} - {self.usage_kind} on {self.subject_kind}"

    def clean(self):
        """Validate that only one of resource_id or asset_id is set"""
        from django.core.exceptions import ValidationError

        if self.subject_kind == "resource" and not self.resource_id:
            raise ValidationError(
                "resource_id must be set when subject_kind is 'resource'",
            )

        if self.subject_kind == "asset" and not self.asset_id:
            raise ValidationError("asset_id must be set when subject_kind is 'asset'")

        if self.resource_id and self.asset_id:
            raise ValidationError("Only one of resource_id or asset_id should be set")

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)

    @classmethod
    def track_asset_download(cls, user, asset, ip_address=None, user_agent=""):
        """Track asset download event with async processing"""
        # Try async processing first
        try:
            from .tasks import track_event_async

            event_data = {
                "developer_user_id": user.id,
                "usage_kind": "file_download",
                "subject_kind": "asset",
                "asset_id": asset.id,
                "metadata": {
                    "asset_title": asset.title,
                    "file_size": asset.file_size,
                    "format": asset.format,
                    "category": asset.category,
                },
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
            if track_event_async(event_data):
                return None  # Event queued for async processing
        except ImportError:
            pass

        # Fallback to synchronous creation
        return cls.objects.create(
            developer_user=user,
            usage_kind="file_download",
            subject_kind="asset",
            asset_id=asset.id,
            metadata={
                "asset_title": asset.title,
                "file_size": asset.file_size,
                "format": asset.format,
                "category": asset.category,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def track_asset_view(cls, user, asset, ip_address=None, user_agent=""):
        """Track asset view event"""
        return cls.objects.create(
            developer_user=user,
            usage_kind="view",
            subject_kind="asset",
            asset_id=asset.id,
            metadata={
                "asset_title": asset.title,
                "category": asset.category,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def track_resource_download(cls, user, resource, ip_address=None, user_agent=""):
        """Track resource download event"""
        latest_version = resource.get_latest_version()
        return cls.objects.create(
            developer_user=user,
            usage_kind="file_download",
            subject_kind="resource",
            resource_id=resource.id,
            metadata={
                "resource_name": resource.name,
                "version": latest_version.semvar if latest_version else "unknown",
                "category": resource.category,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def track_api_access(
        cls,
        user,
        resource=None,
        asset=None,
        api_endpoint="",
        ip_address=None,
        user_agent="",
    ):
        """Track API access event"""
        if resource:
            return cls.objects.create(
                developer_user=user,
                usage_kind="api_access",
                subject_kind="resource",
                resource_id=resource.id,
                metadata={
                    "api_endpoint": api_endpoint,
                    "resource_name": resource.name,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )
        if asset:
            return cls.objects.create(
                developer_user=user,
                usage_kind="api_access",
                subject_kind="asset",
                asset_id=asset.id,
                metadata={
                    "api_endpoint": api_endpoint,
                    "asset_title": asset.title,
                },
                ip_address=ip_address,
                user_agent=user_agent,
            )

    @classmethod
    def get_user_stats(cls, user):
        """Get usage statistics for a user"""
        events = cls.objects.filter(developer_user=user)

        return {
            "total_events": events.count(),
            "downloads": events.filter(usage_kind="file_download").count(),
            "views": events.filter(usage_kind="view").count(),
            "api_calls": events.filter(usage_kind="api_access").count(),
            "asset_interactions": events.filter(subject_kind="asset").count(),
            "resource_interactions": events.filter(subject_kind="resource").count(),
        }

    @classmethod
    def get_asset_stats(cls, asset):
        """Get usage statistics for an asset"""
        events = cls.objects.filter(asset_id=asset.id)

        return {
            "total_events": events.count(),
            "downloads": events.filter(usage_kind="file_download").count(),
            "views": events.filter(usage_kind="view").count(),
            "api_calls": events.filter(usage_kind="api_access").count(),
            "unique_users": events.values("developer_user").distinct().count(),
        }

    @classmethod
    def get_resource_stats(cls, resource):
        """Get usage statistics for a resource"""
        events = cls.objects.filter(resource_id=resource.id)

        return {
            "total_events": events.count(),
            "downloads": events.filter(usage_kind="file_download").count(),
            "views": events.filter(usage_kind="view").count(),
            "api_calls": events.filter(usage_kind="api_access").count(),
            "unique_users": events.values("developer_user").distinct().count(),
        }


# ============================================================================
# 11. DISTRIBUTION (CHANNEL)
# ============================================================================
class Distribution(BaseModel):
    """
    Distribution channels for accessing resource content.
    Defines different delivery methods (API, ZIP download, etc).
    """

    FORMAT_TYPE_CHOICES = [
        ("REST_JSON", "REST API (JSON)"),
        ("GraphQL", "GraphQL API"),
        ("ZIP", "ZIP Download"),
        ("API", "Custom API"),
    ]

    # Relationship
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="distributions",
        help_text="Resource that this distribution provides access to",
    )

    # Distribution details
    format_type = models.CharField(
        max_length=20,
        choices=FORMAT_TYPE_CHOICES,
        help_text="Format/method for accessing the resource",
    )

    endpoint_url = models.URLField(
        validators=[URLValidator()],
        help_text="API endpoint or download URL for accessing content",
    )

    version = models.CharField(
        max_length=50,
        help_text="Distribution version identifier",
    )

    access_config = models.JSONField(
        default=dict,
        help_text="Access configuration (API keys, rate limits, authentication)",
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Format-specific metadata and configuration",
    )

    # Managers
    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        db_table = "distribution"
        verbose_name = "Distribution"
        verbose_name_plural = "Distributions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["resource"]),
            models.Index(fields=["format_type"]),
        ]
        unique_together = [["resource", "format_type", "version"]]

    def __str__(self):
        return f"{self.resource.name} - {self.format_type} v{self.version}"

    def get_access_method(self):
        """Get the appropriate access method based on format type"""
        method_map = {
            "REST_JSON": "GET",
            "GraphQL": "POST",
            "ZIP": "GET",
            "API": "GET",
        }
        return method_map.get(self.format_type, "GET")

    def get_content_type(self):
        """Get the content type for the distribution"""
        content_type_map = {
            "REST_JSON": "application/json",
            "GraphQL": "application/json",
            "ZIP": "application/zip",
            "API": "application/json",
        }
        return content_type_map.get(self.format_type, "application/octet-stream")

    def is_api_endpoint(self):
        """Check if this distribution is an API endpoint"""
        return self.format_type in ["REST_JSON", "GraphQL", "API"]

    def is_download_endpoint(self):
        """Check if this distribution is a download endpoint"""
        return self.format_type == "ZIP"

    def get_authentication_requirements(self):
        """Get authentication requirements from access_config"""
        return self.access_config.get("authentication", {})

    def get_rate_limits(self):
        """Get rate limit configuration"""
        return self.access_config.get("rate_limits", {})

    def get_api_keys(self):
        """Get API key requirements"""
        return self.access_config.get("api_keys", [])

    @classmethod
    def create_rest_api_distribution(
        cls,
        resource,
        endpoint_url,
        version,
        api_config=None,
    ):
        """Create a REST API distribution for a resource"""
        return cls.objects.create(
            resource=resource,
            format_type="REST_JSON",
            endpoint_url=endpoint_url,
            version=version,
            access_config=api_config
            or {
                "authentication": {"required": True},
                "rate_limits": {"requests_per_minute": 100},
            },
            metadata={"response_format": "json", "pagination": True},
        )

    @classmethod
    def create_zip_distribution(cls, resource, download_url, version):
        """Create a ZIP download distribution for a resource"""
        return cls.objects.create(
            resource=resource,
            format_type="ZIP",
            endpoint_url=download_url,
            version=version,
            access_config={"authentication": {"required": True}},
            metadata={"compression": "zip", "includes_all_assets": True},
        )

    @classmethod
    def create_graphql_distribution(cls, resource, graphql_endpoint, version):
        """Create a GraphQL distribution for a resource"""
        return cls.objects.create(
            resource=resource,
            format_type="GraphQL",
            endpoint_url=graphql_endpoint,
            version=version,
            access_config={
                "authentication": {"required": True},
                "rate_limits": {"requests_per_minute": 50},
            },
            metadata={"schema_version": version, "supports_introspection": True},
        )
        return self.format_type in ["REST_JSON", "GraphQL", "API"]

    def is_download(self):
        """Check if this is a downloadable resource"""
        return self.format_type == "ZIP"

    def get_rate_limit(self):
        """Get rate limit from access config"""
        return self.access_config.get("rate_limit", {})

    def requires_api_key(self):
        """Check if API key is required"""
        return self.access_config.get("requires_api_key", False)
