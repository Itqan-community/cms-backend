"""Asset download statistics imported from Cloudflare edge analytics.

`asset_id` / `asset_version_id` are plain integers, not foreign keys: deleting an
asset must not cascade into or block on its history, and the sync must not depend on
the asset row existing.
"""

from django.contrib.postgres.indexes import BrinIndex
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


# ---------------------------------------------------------------------------
# Usage reports: every edge request (Cloudflare Logpush) and Django usage event.
# ---------------------------------------------------------------------------

TRAFFIC_DIMENSIONS: tuple[str, ...] = (
    "asset_id",
    "kind",
    "surah",
    "asset_version_id",
    "language",
    "country",
    "channel",
    "platform",
    "app_id",
    "endpoint",
)


class TrafficSource(models.TextChoices):
    EDGE = "edge"
    DJANGO = "django"


class TrafficKind(models.TextChoices):
    AUDIO_SURAH = "audio_surah"
    AUDIO_AYAH = "audio_ayah"
    VERSION_FILE = "version_file"
    GALLERY_DOWNLOAD = "gallery_download"
    API_CALL = "api_call"
    CLI_INSTALL = "cli_install"
    VIEW = "view"


class TrafficChannel(models.TextChoices):
    GALLERY = "gallery"
    CLI = "cli"
    APP_IDENTIFIED = "app_identified"
    WEB = "web"
    APP_UNIDENTIFIED = "app_unidentified"
    SCRIPT = "script"
    OTHER = "other"


class TrafficPlatform(models.TextChoices):
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
    DESKTOP = "desktop"
    SERVER = "server"
    UNKNOWN = "unknown"


class TrafficStatusClass(models.TextChoices):
    FULL = "full"  # 200
    PARTIAL = "partial"  # 206
    SUCCESS = "success"  # other 2xx
    REDIRECT = "redirect"  # 3xx
    CLIENT_ERROR = "client_error"  # 4xx
    SERVER_ERROR = "server_error"  # 5xx
    OTHER = "other"


class UniqueScope(models.TextChoices):
    ALL = "all"
    ASSET = "asset"
    PUBLISHER = "publisher"
    APP = "app"


class UniqueMeasure(models.TextChoices):
    LISTENERS = "listeners"
    DOWNLOADERS = "downloaders"
    INSTALLS = "installs"
    END_USERS = "end_users"


AUDIO_KINDS = (TrafficKind.AUDIO_SURAH, TrafficKind.AUDIO_AYAH)
# Kinds whose sessions follow the play rule (same listener + same file within the window = one).
FILE_SESSION_KINDS = (*AUDIO_KINDS, TrafficKind.VERSION_FILE, TrafficKind.GALLERY_DOWNLOAD)
# Kinds where every counted request is one session.
EVENT_COUNTED_KINDS = (TrafficKind.API_CALL, TrafficKind.VIEW)
# Requests that count at all: successes and redirects (errors and bots never count).
COUNTED_STATUSES = (
    TrafficStatusClass.FULL,
    TrafficStatusClass.PARTIAL,
    TrafficStatusClass.SUCCESS,
    TrafficStatusClass.REDIRECT,
)
# Requests that delivered file content and can start a play or download.
SESSION_STATUSES = (TrafficStatusClass.FULL, TrafficStatusClass.PARTIAL)


class _TrafficDimensions(models.Model):
    asset_id = models.PositiveIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=16, choices=TrafficKind)
    surah = models.PositiveSmallIntegerField(null=True, blank=True)
    asset_version_id = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=10, blank=True, default="")
    country = models.CharField(max_length=2)
    channel = models.CharField(max_length=16, choices=TrafficChannel)
    platform = models.CharField(max_length=8, choices=TrafficPlatform)
    app_id = models.PositiveIntegerField(null=True, blank=True)
    endpoint = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        abstract = True


class _TrafficMetrics(_TrafficDimensions):
    requests = models.BigIntegerField(default=0)
    bytes = models.BigIntegerField(default=0)
    # Plays (audio), downloads (files), installs (CLI) or calls/views, by kind.
    sessions = models.BigIntegerField(default=0)

    class Meta:
        abstract = True


class TrafficEvent(_TrafficDimensions):
    """One edge request or Django usage event. Client identities are HMACs, never raw values."""

    ray_id = models.CharField(max_length=64, unique=True)  # Cloudflare RayID, or "django:<pk>"
    occurred_at = models.DateTimeField()
    source = models.CharField(max_length=8, choices=TrafficSource, default=TrafficSource.EDGE)
    path = models.CharField(max_length=512, blank=True, default="")
    app_slug_raw = models.CharField(max_length=64, blank=True, default="")
    status_class = models.CharField(max_length=12, choices=TrafficStatusClass)
    bytes = models.BigIntegerField(default=0)
    cache_status = models.CharField(max_length=16, blank=True, default="")
    listener_id = models.CharField(max_length=64)
    end_user_id = models.CharField(max_length=64, blank=True, default="")
    install_id = models.CharField(max_length=64, blank=True, default="")
    ua_family = models.CharField(max_length=32)
    client_name = models.CharField(max_length=64, blank=True, default="")
    client_version = models.CharField(max_length=32, blank=True, default="")
    is_bot = models.BooleanField(default=False)

    class Meta:
        indexes = [
            BrinIndex(fields=["occurred_at"], name="traffic_event_time_brin"),
            models.Index(fields=["asset_id", "occurred_at"], name="traffic_event_asset_idx"),
            models.Index(fields=["app_id", "occurred_at"], name="traffic_event_app_idx"),
            models.Index(
                fields=["listener_id", "asset_id", "kind", "surah", "asset_version_id", "occurred_at"],
                name="traffic_event_session_idx",
            ),
        ]


class TrafficHourly(_TrafficMetrics):
    hour = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["hour", *TRAFFIC_DIMENSIONS], name="uniq_traffic_hourly", nulls_distinct=False
            ),
        ]
        indexes = [
            models.Index(fields=["asset_id", "hour"], name="traffic_hourly_asset_idx"),
            models.Index(fields=["app_id", "hour"], name="traffic_hourly_app_idx"),
        ]


class TrafficDaily(_TrafficMetrics):
    day = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["day", *TRAFFIC_DIMENSIONS], name="uniq_traffic_daily", nulls_distinct=False
            ),
        ]
        indexes = [
            models.Index(fields=["asset_id", "day"], name="traffic_daily_asset_idx"),
            models.Index(fields=["app_id", "day"], name="traffic_daily_app_idx"),
        ]


class TrafficMonthlyUniques(models.Model):
    """Distinct identities per calendar month (UTC). Kept forever, unlike raw events."""

    month = models.DateField()  # first day of the month
    scope = models.CharField(max_length=10, choices=UniqueScope)
    scope_id = models.BigIntegerField()  # 0 for UniqueScope.ALL
    measure = models.CharField(max_length=12, choices=UniqueMeasure)
    count = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["month", "scope", "scope_id", "measure"], name="uniq_traffic_month"),
        ]


class R2ObjectReadsHourly(models.Model):
    """R2 GetObject reads per object and hour, beside the edge requests seen for it."""

    hour = models.DateTimeField()
    object_key = models.CharField(max_length=512)
    asset_id = models.PositiveIntegerField(null=True, blank=True)
    reads = models.BigIntegerField()
    edge_requests = models.BigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["hour", "object_key"], name="uniq_r2_reads_hour_object")]
        indexes = [models.Index(fields=["asset_id", "hour"], name="r2_reads_asset_idx")]


class LogFileImport(models.Model):
    """A Logpush file that was imported (or skipped with `error`). Makes imports idempotent."""

    key = models.CharField(max_length=512, unique=True)
    rows = models.IntegerField()
    error = models.TextField(blank=True, default="")
    # Hours this file's events touched; rebuilt (rolled_up) after the insert commits, so a run
    # that dies in between is finished by the next one.
    first_hour = models.DateTimeField(null=True, blank=True)
    last_hour = models.DateTimeField(null=True, blank=True)
    rolled_up = models.BooleanField(default=True)
    imported_at = models.DateTimeField(auto_now_add=True)


class UsageImportState(BaseModel):
    """Progress of a usage-reports job: `watermark` meaning is job-specific."""

    key = models.CharField(max_length=64, unique=True)
    watermark = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    # Id-based progress for jobs that walk tables (Django fold-in): source rows and traffic rows.
    cursor = models.BigIntegerField(null=True, blank=True)
    traffic_cursor = models.BigIntegerField(null=True, blank=True)


class UsageApp(BaseModel):
    """An integrating app: one per API key. Kept when the key is deleted so history stays attributed."""

    api_key = models.OneToOneField(
        "users.APIKey", null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_app"
    )
    user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_apps")
    name = models.CharField(max_length=50)
    # Public, non-secret: appended to audio/file URLs as `?c=<slug>`.
    slug = models.SlugField(max_length=40, unique=True)
