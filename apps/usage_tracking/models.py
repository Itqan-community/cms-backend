"""Asset download statistics imported from Cloudflare edge analytics.

`asset_id` / `asset_version_id` are plain integers, not foreign keys: deleting an
asset must not cascade into or block on its history, and the sync must not depend on
the asset row existing.
"""

from django.db import models

from apps.core.models import BaseModel

ROLLUP_DIMENSIONS: tuple[str, ...] = (
    "asset_id",
    "file_kind",
    "surah",
    "asset_version_id",
    "country",
    "status_class",
)


class AssetDownloadFileKind(models.TextChoices):
    SURAH = "surah"
    AYAH = "ayah"
    VERSION = "version"


class AssetDownloadStatusClass(models.TextChoices):
    FULL = "full"  # 200
    PARTIAL = "partial"  # 206
    OTHER = "other"  # anything else, e.g. 304


class _DownloadDimensions(models.Model):
    asset_id = models.PositiveIntegerField()
    file_kind = models.CharField(max_length=8, choices=AssetDownloadFileKind)
    surah = models.PositiveSmallIntegerField(null=True, blank=True)
    asset_version_id = models.PositiveIntegerField(null=True, blank=True)
    country = models.CharField(max_length=2)
    status_class = models.CharField(max_length=8, choices=AssetDownloadStatusClass)

    class Meta:
        abstract = True


class _DownloadMetrics(_DownloadDimensions):
    requests = models.BigIntegerField(default=0)
    bytes = models.BigIntegerField(default=0)
    plays = models.BigIntegerField(default=0)

    class Meta:
        abstract = True


class AssetDownloadEvent(_DownloadDimensions):
    """One edge request for an asset file. Raw client IPs are never stored."""

    ray_id = models.CharField(max_length=32, unique=True)
    occurred_at = models.DateTimeField()
    client_hash = models.CharField(max_length=64)

    class Meta:
        indexes = [
            models.Index(fields=["asset_id", "occurred_at"], name="dl_event_asset_time_idx"),
            models.Index(
                fields=["client_hash", "asset_id", "file_kind", "surah", "asset_version_id", "occurred_at"],
                name="dl_event_play_idx",
            ),
            models.Index(fields=["occurred_at"], name="dl_event_time_idx"),
        ]


class AssetDownloadHourly(_DownloadMetrics):
    hour = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["hour", *ROLLUP_DIMENSIONS], name="uniq_dl_hourly", nulls_distinct=False),
        ]
        indexes = [models.Index(fields=["asset_id", "hour"], name="dl_hourly_asset_idx")]


class AssetDownloadDaily(_DownloadMetrics):
    day = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["day", *ROLLUP_DIMENSIONS], name="uniq_dl_daily", nulls_distinct=False),
        ]
        indexes = [models.Index(fields=["asset_id", "day"], name="dl_daily_asset_idx")]


class UsageSyncState(BaseModel):
    """Progress of a periodic import job. `watermark`: every hour before it is fully stored."""

    key = models.CharField(max_length=64, unique=True)
    watermark = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
