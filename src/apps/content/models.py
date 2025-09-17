
import re

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from src.apps.core.models import BaseModel, ActiveObjectsManager, AllObjectsManager
from src.apps.core.uploads import (
    upload_to_asset_thumbnails,
    upload_to_asset_files,
    upload_to_resource_files,
    upload_to_asset_preview_images
)
from src.apps.publishers.models import Publisher
from src.apps.users.models import User


class LicenseChoice(models.TextChoices):
    CC0 = "CC0", _("Creative Commons Zero")
    CC_BY = "CC BY", _("Creative Commons Attribution")
    CC_BY_SA = "CC BY-SA", _("Creative Commons Attribution-ShareAlike")
    CC_BY_ND = "CC BY-ND", _("Creative Commons Attribution-NoDerivs")
    CC_BY_NC = "CC BY-NC", _("Creative Commons Attribution-NonCommercial")
    CC_BY_NC_SA = "CC BY-NC-SA", _("Creative Commons Attribution-NonCommercial-ShareAlike")
    CC_BY_NC_ND = "CC BY-NC-ND", _("Creative Commons Attribution-NonCommercial-NoDerivs")
    PUBLIC_DOMAIN = "Public Domain", _("Public Domain")
    PROPRIETARY = "Proprietary", _("Proprietary")


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

    license = models.CharField(max_length=50, choices=LicenseChoice.choices,default=LicenseChoice.CC0, help_text="Asset license")

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"Resource(name={self.name} category={self.category})"

    def save(self, *args, **kwargs):
        self.slug = slugify(f"{self.name}({self.publisher.slug})"[:50])
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
        upload_to=upload_to_resource_files,
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
    class CategoryChoice(models.TextChoices):
        RECITATION = "recitation", _("Recitation")
        MUSHAF = "mushaf", _("Mushaf")
        TAFSIR = "tafsir", _("Tafsir")

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="assets")

    name = models.CharField(max_length=255, help_text="Asset name")

    description = models.TextField(help_text="Asset description")

    long_description = models.TextField(blank=True, help_text="Extended description")

    thumbnail_url = models.ImageField(
        upload_to=upload_to_asset_thumbnails,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        help_text="Asset thumbnail image",
    )

    category = models.CharField(
        max_length=20, choices=CategoryChoice.choices, help_text="Asset category matching resource categories"
    )

    license = models.CharField(max_length=50, choices=LicenseChoice.choices, help_text="Asset license")

    file_size = models.CharField(max_length=50, help_text="Human readable file size e.g. '2.5 MB'")

    format = models.CharField(max_length=50, help_text="File format")

    encoding = models.CharField(max_length=50, default="UTF-8", help_text="Text encoding")

    version = models.CharField(max_length=50, help_text="Asset version")

    language = models.CharField(max_length=10, help_text="Asset language code")

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    def __str__(self):
        return f"Asset(name={self.name} category={self.category})"

    @staticmethod
    def _parse_file_size_to_bytes(file_size_str):
        """Convert human readable file size to bytes"""
        if not file_size_str:
            return 0


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
            resource__publisher=self.resource.publisher,
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
        upload_to=upload_to_asset_files,
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

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()


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

class AssetPreview(BaseModel):
    """
    Visual images for an Asset
    """
    asset = models.ForeignKey(
        'Asset',
        on_delete=models.CASCADE,
        related_name='previews'
    )

    image_url = models.ImageField(
        upload_to=upload_to_asset_preview_images,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif', 'webp'])],
        help_text="Preview image"
    )

    order = models.PositiveIntegerField(
        default=1,
        help_text="Display order"
    )

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()


    def __str__(self):
        return f"AssetPreview(asset={self.asset.name} order={self.order})"


class AssetAccessRequest(BaseModel):
    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    class IntendedUseChoice(models.TextChoices):
        COMMERCIAL = "commercial", _("Commercial")
        NON_COMMERCIAL = "non-commercial", _("Non-Commercial")

    developer_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='asset_requests'
    )
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='access_requests'
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.PENDING,
    )
    
    developer_access_reason = models.TextField(
        help_text="Reason for requesting access - used in V1 UI"
    )
    
    intended_use = models.CharField(
        max_length=20,
        choices=IntendedUseChoice.choices,
        help_text="Commercial or non-commercial use"
    )

    admin_response = models.TextField(
        blank=True,
        help_text="Admin response message"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When request was approved"
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_asset_requests'
    )
    

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()



    def __str__(self):
        return f"AssetAccessRequest(user={self.developer_user.email} asset={self.asset.name} status={self.status})"


class AssetAccess(BaseModel):
    asset_access_request = models.OneToOneField(
        AssetAccessRequest,
        on_delete=models.CASCADE,
        related_name='access_grant'
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='asset_accesses'
    )
    
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='user_accesses'
    )
    effective_license = models.CharField(max_length=50, choices=LicenseChoice.choices, help_text="Access license at time of grant")

    granted_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When access was granted"
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When access expires (null = never expires)"
    )
    
    download_url = models.URLField(
        blank=True,
        help_text="Direct download URL, can contain signed URL if needed",
    )
    
    objects = AllObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = ['user', 'asset']

    def __str__(self):
        return f"AssetAccess(user_id={self.user_id} asset_id={self.asset_id})"

    @property
    def is_active(self):
        """Check if access is currently active (not expired)"""
        if not self.expires_at:
            return True  # Never expires
        
        return timezone.now() < self.expires_at

    @property
    def is_expired(self):
        """Check if access has expired"""
        return not self.is_active


class UsageEvent(BaseModel):
    class UsageKindChoice(models.TextChoices):
        FILE_DOWNLOAD = "file_download", _("File Download")
        VIEW = "view", _("View")
        API_ACCESS = "api_access", _("API Access")
    class SubjectKindChoice(models.TextChoices):
        RESOURCE = "resource", _("Resource")
        ASSET = "asset", _("Asset")

    developer_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='usage_events'
    )
    
    usage_kind = models.CharField(
        max_length=20,
        choices=UsageKindChoice.choices,
        help_text="Type of usage event"
    )
    
    subject_kind = models.CharField(
        max_length=20,
        choices=SubjectKindChoice.choices,
        help_text="Whether tracking resource or asset"
    )

    resource_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Resource ID if subject_kind = 'resource'"
    )
    
    asset_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Asset ID if subject_kind = 'asset'"
    )

    metadata = models.JSONField(
        default=dict,
        help_text="Additional event metadata"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="User IP address"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User browser/client information"
    )
    effective_license = models.CharField(max_length=50, choices=LicenseChoice.choices, help_text="License at time of usage")

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(subject_kind='resource', resource_id__isnull=False, asset_id__isnull=True) | models.Q(subject_kind='asset', asset_id__isnull=False, resource_id__isnull=True),
                name='usage_event_subject_kind_consistency'
            )
        ]

    def __str__(self):
        return f"UsageEvent(user={self.developer_user_id} kind={self.usage_kind} subject={self.subject_kind})"



    @classmethod
    def get_user_stats(cls, user):
        """Get usage statistics for a user"""
        events = cls.objects.filter(developer_user=user)
        
        return {
            'total_events': events.count(),
            'downloads': events.filter(usage_kind='file_download').count(),
            'views': events.filter(usage_kind='view').count(),
            'api_calls': events.filter(usage_kind='api_access').count(),
            'asset_interactions': events.filter(subject_kind='asset').count(),
            'resource_interactions': events.filter(subject_kind='resource').count()
        }

    @classmethod
    def get_asset_stats(cls, asset):
        """Get usage statistics for an asset"""
        events = cls.objects.filter(asset_id=asset.id)
        
        return {
            'total_events': events.count(),
            'downloads': events.filter(usage_kind='file_download').count(),
            'views': events.filter(usage_kind='view').count(),
            'api_calls': events.filter(usage_kind='api_access').count(),
            'unique_users': events.values('developer_user').distinct().count()
        }

    @classmethod
    def get_resource_stats(cls, resource):
        """Get usage statistics for a resource"""
        events = cls.objects.filter(resource_id=resource.id)
        
        return {
            'total_events': events.count(),
            'downloads': events.filter(usage_kind='file_download').count(),
            'views': events.filter(usage_kind='view').count(),
            'api_calls': events.filter(usage_kind='api_access').count(),
            'unique_users': events.values('developer_user').distinct().count()
        }

class Distribution(BaseModel):
    class ChannelChoice(models.TextChoices):
        REST_JSON = "REST_JSON", _("REST API (JSON)")
        GraphQL = "GraphQL", _("GraphQL API")
        ZIP = "ZIP", _("ZIP Download")
        API = "API", _("Custom API")

    asset_version = models.ForeignKey(
        AssetVersion,
        on_delete=models.CASCADE,
        related_name='distributions',
        help_text="Resource that this distribution provides access to"
    )
    
    channel = models.CharField(
        max_length=20,
        choices=ChannelChoice.choices,
        help_text="Channel for accessing the asset"
    )

    objects = ActiveObjectsManager()
    all_objects = AllObjectsManager()

    class Meta:
        unique_together = [['asset_version', 'channel']]

    def __str__(self):
        return f"Distribution(asset_version={self.asset_version_id} channel={self.channel})"


