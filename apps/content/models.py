import re

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.mixins.storage import DeleteFilesOnDeleteMixin
from apps.core.models import BaseModel
from apps.core.uploads import (
    upload_to_asset_files,
    upload_to_asset_preview_images,
    upload_to_asset_thumbnails,
    upload_to_recitation_surah_track_files,
    upload_to_reciter_image,
    upload_to_resource_files,
)
from apps.mixins.recitations_helpers import get_mp3_duration_ms
from apps.publishers.models import Publisher
from apps.users.models import User


class LicenseChoice(models.TextChoices):
    CC0 = "CC0", _("Creative Commons Zero")
    CC_BY = "CC-BY", _("Creative Commons Attribution")
    CC_BY_SA = "CC-BY-SA", _("Creative Commons Attribution-ShareAlike")
    CC_BY_ND = "CC-BY-ND", _("Creative Commons Attribution-NoDerivs")
    CC_BY_NC = "CC-BY-NC", _("Creative Commons Attribution-NonCommercial")
    CC_BY_NC_SA = (
        "CC-BY-NC-SA",
        _("Creative Commons Attribution-NonCommercial-ShareAlike"),
    )
    CC_BY_NC_ND = (
        "CC-BY-NC-ND",
        _("Creative Commons Attribution-NonCommercial-NoDerivs"),
    )


class Resource(BaseModel):
    class CategoryChoice(models.TextChoices):
        RECITATION = "recitation", _("Recitation")
        MUSHAF = "mushaf", _("Mushaf")
        TAFSIR = "tafsir", _("Tafsir")
        PROGRAM = "program", _("Program")
        LINGUISTIC = "linguistic", _("Linguistic")
        TRANSLATION = "translation", _("Translation")
        FONT = "font", _("Font")
        SEARCH = "search", _("Search")
        TAJWEED = "tajweed", _("Tajweed")

    class StatusChoice(models.TextChoices):
        DRAFT = "draft", _("Draft")
        READY = "ready", _("Ready")

    publisher = models.ForeignKey(Publisher, on_delete=models.PROTECT, related_name="resources")

    name = models.CharField(max_length=255, help_text="Resource name e.g. 'Tafsir Ibn Katheer CSV'")

    slug = models.SlugField(allow_unicode=True, help_text="URL slug e.g. 'tafsir-ibn-katheer-csv'", db_index=True)

    description = models.TextField(help_text="Resource description")

    category = models.CharField(max_length=20, choices=CategoryChoice.choices, help_text="Simple options in V1")

    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.DRAFT,
        help_text="V1: ready = ready to extract Assets from",
    )

    license = models.CharField(
        max_length=50,
        choices=LicenseChoice,
        default=LicenseChoice.CC0,
        help_text="Asset license",
    )

    def __str__(self):
        return f"Resource(name={self.name} category={self.category})"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name[:50], allow_unicode=True)
        super().save(*args, **kwargs)

    def get_latest_version(self):
        return self.versions.order_by("-created_at").first()


class ResourceVersion(DeleteFilesOnDeleteMixin, BaseModel):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="versions")

    name = models.CharField(
        max_length=255,
        help_text="Version name - V1: same as resource name, V2: updates on content",
    )

    summary = models.TextField(blank=True, help_text="Version summary")

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

    size_bytes = models.PositiveBigIntegerField(default=0, help_text="File size in bytes")

    class Meta:
        verbose_name = "Resource Version"
        verbose_name_plural = "Resource Versions"
        unique_together = ["resource", "semvar"]

    def __str__(self):
        return f"ResourceVersion(resource={self.resource.name} semvar={self.semvar})"

    def save(self, *args, **kwargs):
        # Auto-compute human_readable_size from storage file when available and not set
        if (not self.size_bytes or self.size_bytes == 0) and self.storage_url:
            from contextlib import suppress

            with suppress(Exception):
                # FileField provides size when the file is available
                self.size_bytes = self.storage_url.size or 0

        super().save(*args, **kwargs)


class Asset(DeleteFilesOnDeleteMixin, BaseModel):
    class MaddLevelChoice(models.TextChoices):
        TWASSUT = "twassut", _("Twassut")
        QASR = "qasr", _("Qasr")

    class MeemBehaviorChoice(models.TextChoices):
        SILAH = "silah", _("Silah")
        SKOUN = "skoun", _("Skoun")

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
        max_length=20,
        choices=Resource.CategoryChoice.choices,
        help_text="Asset category matching resource categories",
    )

    license = models.CharField(max_length=50, choices=LicenseChoice, help_text="Asset license")

    file_size = models.CharField(max_length=50, help_text="Human readable file size e.g. '2.5 MB'")

    format = models.CharField(max_length=50, help_text="File format")

    encoding = models.CharField(max_length=50, default="UTF-8", help_text="Text encoding")

    version = models.CharField(max_length=50, help_text="Asset version")

    language = models.CharField(max_length=10, help_text="Asset language code")

    # Recitation-specific fields (maybe needs normalizations later)
    reciter = models.ForeignKey(
        "Reciter",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="Reciter for recitation assets",
    )
    riwayah = models.ForeignKey(
        "Riwayah",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="Riwayah for recitation assets",
    )
    qiraah = models.ForeignKey(
        "Qiraah",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assets",
        help_text="Qiraah for recitation assets",
    )
    madd_level = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=MaddLevelChoice.choices,
        help_text="Madd level for recitation assets",
    )
    meem_behaviour = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=MeemBehaviorChoice.choices,
        help_text="Meem behaviour for recitation assets",
    )
    year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Year of recording for recitation assets",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    category="recitation",
                    reciter__isnull=False,
                    qiraah__isnull=False,
                )
                | models.Q(
                    ~models.Q(category="recitation"),
                    reciter__isnull=True,
                    riwayah__isnull=True,
                    qiraah__isnull=True,
                ),
                name="asset_recitation_fields_consistency",
            )
        ]

    def __str__(self):
        return f"Asset(name={self.name}, category={self.category})"

    def save(self, *args, **kwargs):
        if self.riwayah_id and not self.qiraah_id:
            self.qiraah_id = self.riwayah.qiraah_id
        super().save(*args, **kwargs)

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
        ).exclude(
            id=self.id
        )[:limit]

    def get_latest_version(self):
        return self.versions.order_by("-created_at").first()

    @property
    def human_readable_size(self):
        """Get file size in bytes (computed from human readable)"""
        return self._parse_file_size_to_bytes(self.file_size)


class AssetVersion(DeleteFilesOnDeleteMixin, BaseModel):
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

    size_bytes = models.PositiveBigIntegerField(default=0, help_text="File size in bytes")

    def __str__(self):
        return f"AssetVersion(asset={self.asset.name}, version={self.resource_version.semvar})"

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


class AssetPreview(DeleteFilesOnDeleteMixin, BaseModel):
    """
    Visual images for an Asset
    """

    asset = models.ForeignKey("Asset", on_delete=models.CASCADE, related_name="previews")
    image_url = models.ImageField(
        upload_to=upload_to_asset_preview_images,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        help_text="Preview image",
    )
    title = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    order = models.PositiveIntegerField(default=1, help_text="Display order")

    def __str__(self):
        return f"AssetPreview(asset={self.asset.name}, order={self.order})"


class AssetAccessRequest(BaseModel):
    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    class IntendedUseChoice(models.TextChoices):
        COMMERCIAL = "commercial", _("Commercial")
        NON_COMMERCIAL = "non-commercial", _("Non-Commercial")

    developer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="asset_requests")

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="access_requests")

    status = models.CharField(
        max_length=20,
        choices=StatusChoice.choices,
        default=StatusChoice.PENDING,
    )

    developer_access_reason = models.TextField(help_text="Reason for requesting access - used in V1 UI")

    intended_use = models.CharField(
        max_length=20,
        choices=IntendedUseChoice.choices,
        help_text="Commercial or non-commercial use",
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

    def __str__(self):
        return f"AssetAccessRequest(user={self.developer_user.email}, asset={self.asset.name}, status={self.status})"


class AssetAccess(BaseModel):
    asset_access_request = models.OneToOneField(
        AssetAccessRequest, on_delete=models.CASCADE, related_name="access_grant"
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="asset_accesses")

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="user_accesses")
    effective_license = models.CharField(
        max_length=50,
        choices=LicenseChoice,
        help_text="Access license at time of grant",
    )

    granted_at = models.DateTimeField(auto_now_add=True, help_text="When access was granted")

    expires_at = models.DateTimeField(null=True, blank=True, help_text="When access expires (null = never expires)")

    download_url = models.URLField(
        blank=True,
        help_text="Direct download URL, can contain signed URL if needed",
    )

    class Meta:
        unique_together = ["user", "asset"]

    def __str__(self):
        return f"AssetAccess(user_id={self.user_id}, asset_id={self.asset_id})"

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

    def get_download_url(self):
        """Get the download URL for this access"""
        if self.download_url:
            return self.download_url
        latest_version = self.asset.get_latest_version()
        return latest_version.file_url.url if latest_version and latest_version.file_url else None


class UsageEvent(BaseModel):
    class UsageKindChoice(models.TextChoices):
        FILE_DOWNLOAD = "file_download", _("File Download")
        VIEW = "view", _("View")
        API_ACCESS = "api_access", _("API Access")

    class SubjectKindChoice(models.TextChoices):
        RESOURCE = "resource", _("Resource")
        ASSET = "asset", _("Asset")

    developer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usage_events")

    usage_kind = models.CharField(max_length=20, choices=UsageKindChoice.choices, help_text="Type of usage event")

    subject_kind = models.CharField(
        max_length=20,
        choices=SubjectKindChoice.choices,
        help_text="Whether tracking resource or asset",
    )

    resource_id = models.PositiveIntegerField(
        null=True, blank=True, help_text="Resource ID if subject_kind = 'resource'"
    )

    asset_id = models.PositiveIntegerField(null=True, blank=True, help_text="Asset ID if subject_kind = 'asset'")

    metadata = models.JSONField(default=dict, help_text="Additional event metadata")

    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="User IP address")

    user_agent = models.TextField(blank=True, help_text="User browser/client information")
    effective_license = models.CharField(max_length=50, choices=LicenseChoice, help_text="License at time of usage")

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    subject_kind="resource",
                    resource_id__isnull=False,
                    asset_id__isnull=True,
                )
                | models.Q(
                    subject_kind="asset",
                    asset_id__isnull=False,
                    resource_id__isnull=True,
                ),
                name="usage_event_subject_kind_consistency",
            )
        ]

    def __str__(self):
        return f"UsageEvent(user={self.developer_user_id}, kind={self.usage_kind}, subject={self.subject_kind})"

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


class Distribution(BaseModel):
    class ChannelChoice(models.TextChoices):
        FILE_DOWNLOAD = "FILE_DOWNLOAD", _("File Download")
        API = "API", _("API")
        PACKAGE = "PACKAGE", _("Package")

    asset_version = models.ForeignKey(
        AssetVersion,
        on_delete=models.CASCADE,
        related_name="distributions",
        help_text="Asset version that this distribution provides access to",
    )

    channel = models.CharField(
        max_length=20,
        choices=ChannelChoice.choices,
        help_text="Channel for accessing the asset",
    )

    class Meta:
        unique_together = [["asset_version", "channel"]]

    def __str__(self):
        return f"Distribution(asset={self.asset_version.asset.name}, channel={self.channel})"


class Reciter(BaseModel):
    """Quran reciter/qari (e.g. Mshari Al-Afasi, Saad Al-Ghamidi, etc)"""

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True, db_index=True)
    image_url = models.ImageField(
        upload_to=upload_to_reciter_image,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "gif", "webp"])],
        help_text="Icon/logo image - used in V1 UI: Publisher Page",
    )
    bio = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name[:50], allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Reciter(name={self.name})"


class Qiraah(BaseModel):
    """Quran recitation method/school (e.g. Qiraah Asim, Qiraah Nafi, etc)"""

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, allow_unicode=True, db_index=True)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name[:50], allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Qiraah(name={self.name})"


class Riwayah(BaseModel):
    """Quran recitation tradition/transmission (e.g. Hafs, Warsh, etc)"""

    qiraah = models.ForeignKey(
        Qiraah,
        on_delete=models.PROTECT,
        related_name="riwayahs",
        help_text="Parent Qiraah (recitation method)",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(allow_unicode=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["qiraah", "name"]]
        indexes = [
            models.Index(fields=["qiraah", "slug"]),
        ]

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name[:50], allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Riwayah(name={self.name})"


class RecitationSurahTrack(DeleteFilesOnDeleteMixin, BaseModel):
    """Audio track per-surah for a recitation Asset"""

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="recitation_tracks",
        help_text="Parent Asset representing the recitation set",
    )
    surah_number = models.PositiveSmallIntegerField(
        help_text="Surah number (1..114)",
        validators=[MinValueValidator(1), MaxValueValidator(114)],
    )
    audio_file = models.FileField(
        upload_to=upload_to_recitation_surah_track_files,
        validators=[FileExtensionValidator(allowed_extensions=["mp3"])],
        help_text="Per-surah audio file (MP3)",
    )
    original_filename = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Original filename provided at upload time (for audit/debugging; not used as storage key)",
    )
    duration_ms = models.PositiveIntegerField(
        default=0,
        help_text="Audio track duration in milliseconds (auto-calculated upon uploading file)",
    )
    size_bytes = models.PositiveBigIntegerField(
        default=0, help_text="Audio file size in bytes (auto-calculated upon uploading file)"
    )
    upload_finished_at = models.DateTimeField(null=True, blank=True, help_text="When audio file upload was completed")

    class Meta:
        unique_together = [["asset", "surah_number"]]
        indexes = [
            models.Index(fields=["asset", "surah_number"]),
        ]

    def __str__(self) -> str:
        return f"RecitationSurahTrack(asset={self.asset_id}, surah={self.surah_number})"

    def save(self, *args, **kwargs) -> None:
        # Auto-compute duration and size when an MP3 file is present. And set the original filename for admin/manual uploads.
        if self.audio_file:
            try:
                self.size_bytes = int(getattr(self.audio_file, "size", 0) or 0)
            except Exception:
                self.size_bytes = 0

            if not self.duration_ms:
                self.duration_ms = get_mp3_duration_ms(self.audio_file)

            # Preserve the original uploaded filename (admin/manual uploads), without coupling storage keys to user input.
            # For direct-to-R2 upload this is set explicitly by the upload service.
            if not self.original_filename:
                self.original_filename = self.audio_file.name

        super().save(*args, **kwargs)


class RecitationAyahTiming(BaseModel):
    """Timing information per-ayah within a RecitationSurahTrack"""

    track = models.ForeignKey(RecitationSurahTrack, on_delete=models.CASCADE, related_name="ayah_timings")
    ayah_key = models.CharField(max_length=20, help_text='Format "surah_number:ayah_number" e.g. "2:255"')
    start_ms = models.PositiveIntegerField(help_text="Start offset in milliseconds")
    end_ms = models.PositiveIntegerField(help_text="End offset in milliseconds")
    duration_ms = models.PositiveIntegerField(
        default=0, help_text="Duration in milliseconds (auto-calculated as end_ms - start_ms)"
    )

    class Meta:
        unique_together = [["track", "ayah_key"]]

    def __str__(self) -> str:
        return f"RecitationAyahTiming(track={self.track_id}, ayah_key={self.ayah_key})"

    def save(self, *args, **kwargs) -> None:
        # Auto compute ayah duration
        try:
            self.duration_ms = max(0, int(self.end_ms) - int(self.start_ms))
        except Exception:
            self.duration_ms = 0
        super().save(*args, **kwargs)
