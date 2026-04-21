import logging
import re

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from apps.core.mixins.storage import DeleteFilesOnDeleteMixin
from apps.core.models import BaseModel
from apps.core.uploads import (
    upload_to_asset_files,
    upload_to_asset_preview_images,
    upload_to_asset_thumbnails,
    upload_to_recitation_surah_track_files,
    upload_to_reciter_image,
)
from apps.mixins.recitations_helpers import get_mp3_duration_ms
from apps.publishers.models import Publisher
from apps.users.models import User

logger = logging.getLogger(__name__)


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


class Asset(DeleteFilesOnDeleteMixin, BaseModel):
    class MaddLevelChoice(models.TextChoices):
        TWASSUT = "twassut", _("Twassut")
        QASR = "qasr", _("Qasr")

    class MeemBehaviourChoice(models.TextChoices):
        SILAH = "silah", _("Silah")
        SKOUN = "skoun", _("Skoun")

    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.PROTECT,
        related_name="assets",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoice,
        default=StatusChoice.DRAFT,
    )

    name = models.CharField(max_length=255, help_text="Asset name")

    slug = models.SlugField(
        allow_unicode=True, unique=True, db_index=True, default="", help_text="URL-friendly slug for the asset"
    )

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
        choices=CategoryChoice,
        help_text="Asset category matching resource categories",
    )

    license = models.CharField(max_length=50, choices=LicenseChoice, help_text="Asset license")

    file_size = models.CharField(max_length=50, help_text="Human readable file size e.g. '2.5 MB'")

    format = models.CharField(max_length=50, help_text="File format")

    encoding = models.CharField(max_length=50, default="UTF-8", help_text="Text encoding")

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
        choices=MeemBehaviourChoice.choices,
        help_text="Meem behaviour for recitation assets",
    )
    year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Year of recording for recitation assets",
    )

    is_external = models.BooleanField(
        default=False,
        help_text="Whether this asset is external",
    )
    external_url = models.URLField(
        "External URL",
        null=True,
        blank=True,
        help_text="URL for external assets",
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
            ),
            models.CheckConstraint(
                condition=models.Q(is_external=False, external_url__isnull=True)
                | models.Q(is_external=True, external_url__isnull=False),
                name="asset_external_url_consistency",
            ),
        ]

    def __str__(self):
        return f"Asset(name={self.name}, category={self.category})"

    def save(self, *args, **kwargs):
        if self.riwayah_id and not self.qiraah_id:
            self.qiraah_id = self.riwayah.qiraah_id
        if not self.slug:
            from django.utils.text import slugify

            base_slug = slugify(self.name[:50], allow_unicode=True) or f"asset-{self.pk or 0}"
            slug = base_slug
            counter = 1
            while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug[:40]}-{counter}"
                counter += 1
            self.slug = slug
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

    def get_latest_version(self):
        return self.versions.order_by("-created_at").first()

    @property
    def human_readable_size(self):
        """Get file size in bytes (computed from human readable)"""
        return self._parse_file_size_to_bytes(self.file_size)


class AssetVersion(DeleteFilesOnDeleteMixin, BaseModel):
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="versions")

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
        return f"AssetVersion(asset={self.asset.name}, name={self.name})"

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

    developer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="asset_requests", db_index=True)

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="access_requests", db_index=True)

    status = models.CharField(
        max_length=20,
        choices=StatusChoice,
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

    class Meta:
        indexes = [
            models.Index(fields=["developer_user", "asset"]),
        ]

    def __str__(self):
        return f"AssetAccessRequest(user={self.developer_user.email}, asset={self.asset.name}, status={self.status})"


class AssetAccess(BaseModel):
    asset_access_request = models.OneToOneField(
        AssetAccessRequest, on_delete=models.CASCADE, related_name="access_grant"
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="asset_accesses", db_index=True)

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="user_accesses", db_index=True)
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

    developer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usage_events", db_index=True)

    usage_kind = models.CharField(max_length=20, choices=UsageKindChoice.choices, help_text="Type of usage event")

    asset_id = models.PositiveIntegerField(help_text="Asset ID the event refers to")

    metadata = models.JSONField(default=dict, help_text="Additional event metadata")

    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="User IP address")

    user_agent = models.TextField(blank=True, help_text="User browser/client information")
    effective_license = models.CharField(max_length=50, choices=LicenseChoice, help_text="License at time of usage")

    class Meta:
        indexes = [
            models.Index(fields=["developer_user", "usage_kind"]),
            models.Index(fields=["created_at", "usage_kind"]),
        ]

    def __str__(self):
        return f"UsageEvent(user={self.developer_user_id}, kind={self.usage_kind}, asset={self.asset_id})"

    @classmethod
    def get_user_stats(cls, user):
        """Get usage statistics for a user"""
        events = cls.objects.filter(developer_user=user)

        return {
            "total_events": events.count(),
            "downloads": events.filter(usage_kind="file_download").count(),
            "views": events.filter(usage_kind="view").count(),
            "api_calls": events.filter(usage_kind="api_access").count(),
            "asset_interactions": events.count(),
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
    date_of_death = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    nationality = CountryField(blank=True, default="")

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
    bio = models.TextField(blank=True)
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
    bio = models.TextField(blank=True)
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
            if not self.size_bytes:
                try:
                    self.size_bytes = int(getattr(self.audio_file, "size", 0) or 0)
                except Exception as e:
                    logger.warning(f"Failed to get file size for RecitationSurahTrack: {e}")
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
        except Exception as e:
            logger.warning(f"Failed to compute ayah duration for {self.ayah_key}: {e}")
            self.duration_ms = 0
        super().save(*args, **kwargs)


class ContentIssueReport(BaseModel):
    """Issue reports for Assets."""

    class StatusChoice(models.TextChoices):
        PENDING = "pending", _("Pending")
        UNDER_REVIEW = "under_review", _("Under Review")
        RESOLVED = "resolved", _("Resolved")
        DISMISSED = "dismissed", _("Dismissed")

    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="content_issue_reports",
        help_text="User who reported the issue",
    )

    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        limit_choices_to={"model__in": ["asset"]},
        help_text="Django ContentType for the reported object",
    )

    object_id = models.PositiveIntegerField(help_text="ID of the reported content object")

    content_object = GenericForeignKey("content_type", "object_id")

    description = models.TextField(
        help_text="Description of the issue (10-2000 characters)",
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoice,
        default=StatusChoice.PENDING,
        help_text="Current status of the issue report",
    )

    class Meta:
        verbose_name = "Content Issue Report"
        verbose_name_plural = "Content Issue Reports"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["reporter", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        content_type_name = self.content_type.model if self.content_type else "unknown"
        return f"ContentIssueReport(reporter={self.reporter_id}, content={content_type_name}:{self.object_id}, status={self.status})"

    @property
    def content_object_summary(self) -> str:
        return str(self.content_object)

    def clean(self):
        """Validate the model before saving"""
        from django.core.exceptions import ValidationError

        # Validate description length
        if self.description:
            if len(self.description) < 10:
                raise ValidationError({"description": "Description must be at least 10 characters long."})
            if len(self.description) > 2000:
                raise ValidationError({"description": "Description cannot exceed 2000 characters."})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
