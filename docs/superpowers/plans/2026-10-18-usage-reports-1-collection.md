# Usage Reports — Plan 1: Traffic Collection (backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import every Cloudflare edge request for asset files and public-API routes from Logpush
files in R2 into a new `TrafficEvent` table with channel, platform, bot and stable listener
identity, roll it up hourly/daily/monthly, and record R2 reads as a reconciliation check.

**Architecture:** Three hourly/nightly Celery jobs in `apps/usage_tracking`: a Logpush importer
(R2 → parse → classify → `TrafficEvent` → hour rebuild), an R2 reconciliation import (GraphQL
`r2OperationsAdaptiveGroups` → `R2ObjectReadsHourly`), and a nightly maintenance job (monthly
uniques + retention purge). Pure modules (parser, classifier, identity) are separated from the
repository (all SQL) and the services (orchestration), matching the existing download-stats code.
The 2026-10-13 GraphQL sync keeps running untouched until cutover (plan 6).

**Tech Stack:** Django 5 + Postgres 17, Celery beat, boto3 (R2 S3 API), requests (Cloudflare
GraphQL), pytest + `BaseTestCase`, model_bakery.

**Spec:** `docs/superpowers/specs/2026-10-18-usage-reports-design.md` (§4, §5.1, §6, §7, §8 rows
for requests/plays/downloads/installs/uniques, §13, §14 row 1, §15).

## Global Constraints

- Backend rules (`.agents/rules/cms-backend.mdc`): **never commit** unless the user grants
  permission for this branch; tests use `BaseTestCase` (or plain classes for pure functions), AAA
  comments, names `test_<fn>_where_<criteria>_should_<expected>`; patch with
  `patch.object(target, symbol.__name__)`; every `_()` string localized with 0 untranslated;
  docs updated at the end.
- Run Python with `uv run --frozen` (a bare `uv run` rewrites `uv.lock`; revert it if it does).
- Worktree DB: `DB_NAME=itqan_usage_reports` (already set in `.env`).
- All new settings optional with defaults; every flag defaults to off.
- Raw client IPs are never written to the database by the new pipeline.
- `asset_id`, `asset_version_id`, `app_id` are plain integers, not foreign keys (history must not
  cascade or block on deletes; matches the existing `AssetDownloadEvent`).
- Postgres 17 is available on staging and production (`nulls_distinct=False` is fine).
- `baker.make(Asset, ...)` needs `category=CategoryChoice.MUSHAF` (or FONT); recitations need a
  reciter, tafsir/translation need a template (check constraints).
- Pre-commit formatting: black (line length per `pyproject.toml`), isort, ruff, bandit,
  django-upgrade (`choices=EnumClass`, `headers={...}` in tests).

## Spec amendments made by this plan (apply in Task 9 to the spec)

1. `TrafficEvent.app_id` is a plain integer (spec said FK) — same reason as `asset_id`.
2. `host_env` is dropped: each environment reads its own Logpush prefix, so rows never mix.
3. Hourly/daily rollups do **not** store `unique_listeners` (not additive across rows); unique
   metrics read `TrafficEvent` or `TrafficMonthlyUniques`.
4. `endpoint` is a rollup dimension (developer breakdown by endpoint); events also store `path`.
5. The `app_identified` channel rule and app resolution ship in plan 2 (nothing emits `?c=` yet);
   this plan stores `app_slug_raw` so plan 2 can backfill.
6. `LogFileImport` gains `error` (corrupt files are recorded and skipped, not retried forever).
7. New setting `USAGE_LOGPUSH_MAX_FILES_PER_RUN` (default 500) bounds a backfill run.
8. `end_user_id` hashes `x-client-name + external id` on edge rows (the edge never sees the API
   key); plan 2's Django fallback hashes `app_id + external id`.

## Review Focus

1. A Logpush file re-delivered or re-listed after a crash between insert and bookkeeping →
   no double counts (rows keyed by `RayID`, file recorded in the same transaction).
2. A late file containing events for an hour already rolled up → that hour (and the next one when
   a play may continue) is rebuilt, not left stale.
3. A gzip-truncated or non-JSON file → recorded with `error`, run continues, other files import.
4. Phones whose model names contain "bot" (e.g. `Cubot`) must not be flagged as bots.
5. `/packages/resolve/manifest/` must map to its literal route, not `{slug}` = "manifest".

---

### Task 1: Traffic models and migration

**Files:**
- Modify: `apps/usage_tracking/models.py`
- Create: `apps/usage_tracking/migrations/0002_traffic.py` (generated)
- Test: `apps/usage_tracking/tests/test_traffic_models.py`

**Interfaces:**
- Produces: `TrafficSource`, `TrafficKind`, `TrafficChannel`, `TrafficPlatform`,
  `TrafficStatusClass`, `UniqueScope`, `UniqueMeasure` (TextChoices); constants
  `TRAFFIC_DIMENSIONS`, `AUDIO_KINDS`, `FILE_SESSION_KINDS`, `EVENT_COUNTED_KINDS`,
  `COUNTED_STATUSES`, `SESSION_STATUSES`; models `TrafficEvent`, `TrafficHourly`, `TrafficDaily`,
  `TrafficMonthlyUniques`, `R2ObjectReadsHourly`, `LogFileImport`, `UsageImportState`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_traffic_models.py
from datetime import UTC, datetime

from django.db import IntegrityError, transaction
import pytest

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    TrafficChannel,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficPlatform,
    TrafficStatusClass,
)

AT = datetime(2026, 10, 18, 10, 5, tzinfo=UTC)


def _event(ray_id: str) -> TrafficEvent:
    return TrafficEvent(
        ray_id=ray_id,
        occurred_at=AT,
        kind=TrafficKind.AUDIO_SURAH,
        asset_id=13,
        surah=1,
        country="SA",
        channel=TrafficChannel.APP_UNIDENTIFIED,
        platform=TrafficPlatform.ANDROID,
        status_class=TrafficStatusClass.FULL,
        listener_id="a" * 64,
        ua_family="dalvik",
    )


class TestTrafficModels(BaseTestCase):
    def test_traffic_event_where_ray_id_repeats_should_reject_duplicate(self):
        # Arrange
        _event("ray-1").save()

        # Act / Assert
        with pytest.raises(IntegrityError), transaction.atomic():
            _event("ray-1").save()

    def test_traffic_hourly_where_null_dimensions_repeat_should_reject_duplicate(self):
        # Arrange
        values = {
            "hour": AT.replace(minute=0),
            "asset_id": None,
            "kind": TrafficKind.API_CALL,
            "country": "SA",
            "channel": TrafficChannel.SCRIPT,
            "platform": TrafficPlatform.SERVER,
            "endpoint": "/recitations/",
        }
        TrafficHourly.objects.create(**values)

        # Act / Assert
        with pytest.raises(IntegrityError), transaction.atomic():
            TrafficHourly.objects.create(**values)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_models.py`
Expected: FAIL — `ImportError: cannot import name 'TrafficChannel'`.

- [ ] **Step 3: Add the models** (append to `apps/usage_tracking/models.py`; add the import
  `from django.contrib.postgres.indexes import BrinIndex` at the top)

```python
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
            models.UniqueConstraint(fields=["day", *TRAFFIC_DIMENSIONS], name="uniq_traffic_daily", nulls_distinct=False),
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
    imported_at = models.DateTimeField(auto_now_add=True)


class UsageImportState(BaseModel):
    """Progress of a usage-reports job: `watermark` meaning is job-specific."""

    key = models.CharField(max_length=64, unique=True)
    watermark = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
```

- [ ] **Step 4: Generate the migration**

Run: `uv run --frozen manage.py makemigrations usage_tracking --name traffic`
Expected: `apps/usage_tracking/migrations/0002_traffic.py` with `CreateModel` for the 7 models.
(If `InconsistentMigrationHistory` appears, set a fresh `DB_NAME` per the
local-DB-migration-drift memory and rerun.)

- [ ] **Step 5: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_models.py`
Expected: 2 passed.

- [ ] **Step 6: Checkpoint** — no commit (backend rule). Files: `models.py`,
  `migrations/0002_traffic.py`, `tests/test_traffic_models.py`.

---

### Task 2: Request classification (status, client family, platform, channel, bots)

**Files:**
- Create: `apps/usage_tracking/services/traffic_classify.py`
- Test: `apps/usage_tracking/tests/test_traffic_classify.py`

**Interfaces:**
- Consumes: Task 1 choices.
- Produces: `status_class_for(status: int) -> str`, `ua_family(user_agent: str) -> str`,
  `is_bot_user_agent(user_agent: str) -> bool`, `platform_for(user_agent: str, family: str) -> str`,
  `channel_for(kind: str, family: str, *, has_install_id: bool) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_traffic_classify.py
import pytest

from apps.usage_tracking.models import TrafficChannel, TrafficKind, TrafficPlatform, TrafficStatusClass
from apps.usage_tracking.services.traffic_classify import (
    channel_for,
    is_bot_user_agent,
    platform_for,
    status_class_for,
    ua_family,
)

DALVIK = "Dalvik/2.1.0 (Linux; U; Android 14; SM-A156E Build/UP1A.231005.007)"
IOS = "AppleCoreMedia/1.0.0.21G93 (iPhone; U; CPU OS 17_6_1 like Mac OS X; en_us)"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"
JUST_AUDIO_ANDROID = "just_audio/2.0.7 (Linux;Android 14) ExoPlayerLib/2.18.7"
CUBOT = "Dalvik/2.1.0 (Linux; U; Android 13; Cubot P80 Build/TP1A.220624.014)"


class TestStatusClass:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (200, TrafficStatusClass.FULL),
            (206, TrafficStatusClass.PARTIAL),
            (204, TrafficStatusClass.SUCCESS),
            (304, TrafficStatusClass.REDIRECT),
            (404, TrafficStatusClass.CLIENT_ERROR),
            (503, TrafficStatusClass.SERVER_ERROR),
            (0, TrafficStatusClass.OTHER),
        ],
    )
    def test_status_class_for_where_status_given_should_map_to_class(self, status, expected):
        # Act / Assert
        assert status_class_for(status) == expected


class TestUaFamily:
    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            ("itqan-cli/0.4.0", "itqan-cli"),
            (DALVIK, "dalvik"),
            (IOS, "applecoremedia"),
            (JUST_AUDIO_ANDROID, "exoplayer"),
            ("just_audio/2.0.7 (iOS 17)", "just_audio"),
            ("curl/8.7.1", "curl"),
            ("python-requests/2.32.3", "python"),
            (CHROME, "browser"),
            ("", "empty"),
            ("SomethingElse/1.0", "other"),
        ],
    )
    def test_ua_family_where_user_agent_given_should_name_family(self, user_agent, expected):
        # Act / Assert
        assert ua_family(user_agent) == expected


class TestBots:
    @pytest.mark.parametrize(
        "user_agent",
        [
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
            "facebookexternalhit/1.1",
            "Mozilla/5.0 zgrab/0.x",
        ],
    )
    def test_is_bot_user_agent_where_crawler_should_be_true(self, user_agent):
        # Act / Assert
        assert is_bot_user_agent(user_agent) is True

    @pytest.mark.parametrize("user_agent", [DALVIK, CUBOT, IOS, CHROME, "itqan-cli/0.4.0"])
    def test_is_bot_user_agent_where_real_client_should_be_false(self, user_agent):
        # Act / Assert
        assert is_bot_user_agent(user_agent) is False


class TestPlatform:
    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            (DALVIK, TrafficPlatform.ANDROID),
            (JUST_AUDIO_ANDROID, TrafficPlatform.ANDROID),
            (IOS, TrafficPlatform.IOS),
            (CHROME, TrafficPlatform.WEB),
            ("itqan-cli/0.4.0", TrafficPlatform.DESKTOP),
            ("curl/8.7.1", TrafficPlatform.SERVER),
            ("SomethingElse/1.0", TrafficPlatform.UNKNOWN),
        ],
    )
    def test_platform_for_where_user_agent_given_should_map_platform(self, user_agent, expected):
        # Act / Assert
        assert platform_for(user_agent, ua_family(user_agent)) == expected


class TestChannel:
    @pytest.mark.parametrize(
        ("kind", "family", "has_install_id", "expected"),
        [
            (TrafficKind.GALLERY_DOWNLOAD, "browser", False, TrafficChannel.GALLERY),
            (TrafficKind.VERSION_FILE, "itqan-cli", False, TrafficChannel.CLI),
            (TrafficKind.VERSION_FILE, "python", True, TrafficChannel.CLI),
            (TrafficKind.AUDIO_SURAH, "browser", False, TrafficChannel.WEB),
            (TrafficKind.AUDIO_SURAH, "dalvik", False, TrafficChannel.APP_UNIDENTIFIED),
            (TrafficKind.API_CALL, "curl", False, TrafficChannel.SCRIPT),
            (TrafficKind.AUDIO_SURAH, "other", False, TrafficChannel.OTHER),
        ],
    )
    def test_channel_for_where_inputs_given_should_pick_first_matching_channel(
        self, kind, family, has_install_id, expected
    ):
        # Act / Assert
        assert channel_for(kind, family, has_install_id=has_install_id) == expected
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_classify.py`
Expected: FAIL — `ModuleNotFoundError: ... traffic_classify`.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/services/traffic_classify.py
"""Classifies requests by status, client family, platform, channel and bot traffic.

User agents are attacker-controlled; classification only ever labels a row, it never
decides access, so a spoofed user agent can at worst mislabel its own request.
"""

import re

from apps.usage_tracking.models import TrafficChannel, TrafficKind, TrafficPlatform, TrafficStatusClass

# Crawler conventions ("Name/1.0", "+http://..." contact URL) and known scanners. Deliberately
# not a bare "bot" match: Android phone models such as "Cubot P80" contain it.
_BOT_RE = re.compile(
    r"bot/\d|bot;|\+https?://|spider|crawler|facebookexternalhit|httrack|headlesschrome|"
    r"masscan|zgrab|nuclei|nikto|sqlmap|censys",
    re.IGNORECASE,
)

# Checked in order; the first match names the family.
_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("itqan-cli", re.compile(r"^itqan-cli/", re.IGNORECASE)),
    ("exoplayer", re.compile(r"ExoPlayer", re.IGNORECASE)),
    ("dalvik", re.compile(r"\bDalvik/")),
    ("just_audio", re.compile(r"just_audio", re.IGNORECASE)),
    ("okhttp", re.compile(r"\bokhttp/", re.IGNORECASE)),
    ("dart", re.compile(r"^Dart/")),
    ("applecoremedia", re.compile(r"AppleCoreMedia")),
    ("cfnetwork", re.compile(r"CFNetwork")),
    ("curl", re.compile(r"^curl/", re.IGNORECASE)),
    ("wget", re.compile(r"^Wget/", re.IGNORECASE)),
    ("python", re.compile(r"python-requests|python-urllib|aiohttp|httpx", re.IGNORECASE)),
    ("node", re.compile(r"^node|axios|undici|node-fetch", re.IGNORECASE)),
    ("go", re.compile(r"Go-http-client")),
    ("browser", re.compile(r"^Mozilla/")),
)
_APP_FAMILIES = frozenset({"exoplayer", "dalvik", "just_audio", "okhttp", "dart", "applecoremedia", "cfnetwork"})
_SCRIPT_FAMILIES = frozenset({"curl", "wget", "python", "node", "go", "empty"})
_ANDROID_RE = re.compile(r"Android", re.IGNORECASE)
_IOS_RE = re.compile(r"iPhone|iPad|iPod|\biOS\b|CPU OS", re.IGNORECASE)


def status_class_for(status: int) -> str:
    if status == 200:
        return TrafficStatusClass.FULL
    if status == 206:
        return TrafficStatusClass.PARTIAL
    if 200 <= status < 300:
        return TrafficStatusClass.SUCCESS
    if 300 <= status < 400:
        return TrafficStatusClass.REDIRECT
    if 400 <= status < 500:
        return TrafficStatusClass.CLIENT_ERROR
    if 500 <= status < 600:
        return TrafficStatusClass.SERVER_ERROR
    return TrafficStatusClass.OTHER


def ua_family(user_agent: str) -> str:
    if not user_agent.strip():
        return "empty"
    for family, pattern in _FAMILIES:
        if pattern.search(user_agent):
            return family
    return "other"


def is_bot_user_agent(user_agent: str) -> bool:
    return bool(_BOT_RE.search(user_agent))


def platform_for(user_agent: str, family: str) -> str:
    if family == "browser":
        return TrafficPlatform.WEB
    if family == "itqan-cli":
        return TrafficPlatform.DESKTOP
    if family in _SCRIPT_FAMILIES:
        return TrafficPlatform.SERVER
    if family in {"dalvik", "exoplayer", "okhttp"} or _ANDROID_RE.search(user_agent):
        return TrafficPlatform.ANDROID
    if family in {"applecoremedia", "cfnetwork"} or _IOS_RE.search(user_agent):
        return TrafficPlatform.IOS
    return TrafficPlatform.UNKNOWN


def channel_for(kind: str, family: str, *, has_install_id: bool) -> str:
    """First matching rule wins (spec §5.1). `app_identified` is added in plan 2."""
    if kind == TrafficKind.GALLERY_DOWNLOAD:
        return TrafficChannel.GALLERY
    if family == "itqan-cli" or has_install_id:
        return TrafficChannel.CLI
    if family == "browser":
        return TrafficChannel.WEB
    if family in _APP_FAMILIES:
        return TrafficChannel.APP_UNIDENTIFIED
    if family in _SCRIPT_FAMILIES:
        return TrafficChannel.SCRIPT
    return TrafficChannel.OTHER
```

- [ ] **Step 4: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_classify.py`
Expected: all passed.

- [ ] **Step 5: Checkpoint** — no commit.

---

### Task 3: Stable identities and the identity-key check

**Files:**
- Create: `apps/usage_tracking/services/traffic_identity.py`, `apps/usage_tracking/checks.py`
- Modify: `apps/usage_tracking/apps.py`, `config/settings/base.py` (usage-reports settings block)
- Test: `apps/usage_tracking/tests/test_traffic_identity.py`

**Interfaces:**
- Produces: `listener_id_for(ip: str, user_agent: str, ray_id: str) -> str`,
  `end_user_id_for(app_key: str, external_user_id: str) -> str`,
  `install_id_for(raw: str) -> str`, `check_usage_identity_key(app_configs=None, **kwargs) -> list`.
- Produces settings (all in one block, used by later tasks):
  `ENABLE_USAGE_LOGPUSH_IMPORT`, `USAGE_LOGS_BUCKET`, `USAGE_LOGS_PREFIX`,
  `USAGE_LOGS_ACCESS_KEY_ID`, `USAGE_LOGS_SECRET_ACCESS_KEY`, `USAGE_LOGPUSH_MAX_FILES_PER_RUN`,
  `ENABLE_USAGE_R2_RECONCILIATION`, `CF_ACCOUNT_ID`, `USAGE_ANALYTICS_API_TOKEN`,
  `USAGE_IDENTITY_KEY`, `USAGE_EVENT_RETENTION_MONTHS`.

- [ ] **Step 1: Add the settings** (in `config/settings/base.py`, directly after the
  `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` block)

```python
# Usage reports: Cloudflare Logpush import (every edge request) and R2 read reconciliation.
# All optional; both jobs are off until enabled.
ENABLE_USAGE_LOGPUSH_IMPORT = config("ENABLE_USAGE_LOGPUSH_IMPORT", default=False, cast=bool)
USAGE_LOGS_BUCKET = config("USAGE_LOGS_BUCKET", default="itqan-usage-logs")
USAGE_LOGS_PREFIX = config("USAGE_LOGS_PREFIX", default="http/production/")
USAGE_LOGS_ACCESS_KEY_ID = config("USAGE_LOGS_ACCESS_KEY_ID", default="")
USAGE_LOGS_SECRET_ACCESS_KEY = config("USAGE_LOGS_SECRET_ACCESS_KEY", default="")
USAGE_LOGPUSH_MAX_FILES_PER_RUN = config("USAGE_LOGPUSH_MAX_FILES_PER_RUN", default=500, cast=int)
ENABLE_USAGE_R2_RECONCILIATION = config("ENABLE_USAGE_R2_RECONCILIATION", default=False, cast=bool)
CF_ACCOUNT_ID = config("CF_ACCOUNT_ID", default="")
# Needs Account Analytics Read; falls back to CF_API_TOKEN.
USAGE_ANALYTICS_API_TOKEN = config("USAGE_ANALYTICS_API_TOKEN", default="") or CF_API_TOKEN
# Never rotate: listener/install/end-user ids are HMACs under this key. Empty derives from SECRET_KEY.
USAGE_IDENTITY_KEY = config("USAGE_IDENTITY_KEY", default="")
USAGE_EVENT_RETENTION_MONTHS = config("USAGE_EVENT_RETENTION_MONTHS", default=25, cast=int)
```

- [ ] **Step 2: Write the failing tests**

```python
# apps/usage_tracking/tests/test_traffic_identity.py
import pytest

from apps.usage_tracking.checks import check_usage_identity_key
from apps.usage_tracking.services.traffic_identity import end_user_id_for, install_id_for, listener_id_for


class TestIdentity:
    @pytest.fixture(autouse=True)
    def _keys(self, settings):
        settings.SECRET_KEY = "secret-a"
        settings.USAGE_IDENTITY_KEY = ""

    def test_listener_id_for_where_same_ip_and_agent_should_be_stable(self):
        # Act
        first = listener_id_for("203.0.113.7", "Dalvik/2.1.0", "ray-1")
        second = listener_id_for("203.0.113.7", "Dalvik/2.1.0", "ray-2")

        # Assert
        assert first == second
        assert len(first) == 64
        assert "203.0.113.7" not in first

    def test_listener_id_for_where_agent_differs_should_differ(self):
        # Act / Assert
        assert listener_id_for("203.0.113.7", "A", "r") != listener_id_for("203.0.113.7", "B", "r")

    def test_listener_id_for_where_ip_missing_should_use_ray_so_requests_never_merge(self):
        # Act / Assert
        assert listener_id_for("", "A", "ray-1") != listener_id_for("", "A", "ray-2")

    def test_listener_id_for_where_identity_key_set_should_ignore_secret_key(self, settings):
        # Arrange
        settings.USAGE_IDENTITY_KEY = "identity"
        before = listener_id_for("203.0.113.7", "A", "r")

        # Act
        settings.SECRET_KEY = "secret-b"

        # Assert
        assert listener_id_for("203.0.113.7", "A", "r") == before

    def test_end_user_id_for_where_no_external_id_should_be_empty(self):
        # Act / Assert
        assert end_user_id_for("quran-companion", "") == ""

    def test_end_user_id_for_where_same_user_in_two_apps_should_differ(self):
        # Act / Assert
        assert end_user_id_for("app-a", "u1") != end_user_id_for("app-b", "u1")

    def test_install_id_for_where_raw_given_should_hash_it(self):
        # Act
        result = install_id_for("0b1c-uuid")

        # Assert
        assert len(result) == 64
        assert install_id_for("") == ""


class TestIdentityCheck:
    def test_check_usage_identity_key_where_import_enabled_without_key_should_warn(self, settings):
        # Arrange
        settings.ENABLE_USAGE_LOGPUSH_IMPORT = True
        settings.USAGE_IDENTITY_KEY = ""

        # Act
        messages = check_usage_identity_key()

        # Assert
        assert [message.id for message in messages] == ["usage_tracking.W001"]

    def test_check_usage_identity_key_where_key_set_should_pass(self, settings):
        # Arrange
        settings.ENABLE_USAGE_LOGPUSH_IMPORT = True
        settings.USAGE_IDENTITY_KEY = "identity"

        # Act / Assert
        assert check_usage_identity_key() == []
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_identity.py`
Expected: FAIL — `ModuleNotFoundError: apps.usage_tracking.checks`.

- [ ] **Step 4: Implement**

```python
# apps/usage_tracking/services/traffic_identity.py
"""Pseudonymous, stable client identities (HMAC-SHA256 under USAGE_IDENTITY_KEY).

Stable across days so unique counts work over any range; raw values are never stored.
"""

import hashlib
import hmac

from django.conf import settings


def _identity_key() -> bytes:
    if settings.USAGE_IDENTITY_KEY:
        return settings.USAGE_IDENTITY_KEY.encode()
    return hashlib.sha256(f"usage-identity:{settings.SECRET_KEY}".encode()).digest()


def _hmac(value: str) -> str:
    return hmac.new(_identity_key(), value.encode(), hashlib.sha256).hexdigest()


def listener_id_for(ip: str, user_agent: str, ray_id: str) -> str:
    # Without an IP, fall back to the request itself so IP-less requests never merge.
    return _hmac(f"listener:{ip}|{user_agent}" if ip else f"ray:{ray_id}")


def end_user_id_for(app_key: str, external_user_id: str) -> str:
    return _hmac(f"user:{app_key}|{external_user_id}") if external_user_id else ""


def install_id_for(raw: str) -> str:
    return _hmac(f"install:{raw}") if raw else ""
```

```python
# apps/usage_tracking/checks.py
from django.conf import settings
from django.core.checks import Warning as CheckWarning


def check_usage_identity_key(app_configs=None, **kwargs) -> list[CheckWarning]:
    if settings.USAGE_IDENTITY_KEY or not settings.ENABLE_USAGE_LOGPUSH_IMPORT:
        return []
    return [
        CheckWarning(
            "USAGE_IDENTITY_KEY is not set; unique-listener ids derive from SECRET_KEY, "
            "so rotating SECRET_KEY resets all unique counts.",
            id="usage_tracking.W001",
        )
    ]
```

In `apps/usage_tracking/apps.py`, add to `UsageTrackingConfig`:

```python
    def ready(self) -> None:
        from django.core import checks

        from apps.usage_tracking.checks import check_usage_identity_key

        checks.register(check_usage_identity_key)
```

(If `UsageTrackingConfig` already defines `ready`, append the two registration lines to it.)

- [ ] **Step 5: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_identity.py`
Expected: all passed.

- [ ] **Step 6: Checkpoint** — no commit.

---

### Task 4: Logpush line parser

**Files:**
- Modify: `apps/usage_tracking/services/download_paths.py` (rename `_db_integer` → `db_integer`,
  `_SURAH_RANGE` → `SURAH_RANGE`; update their uses in the same file)
- Create: `apps/usage_tracking/services/logpush_parser.py`
- Test: `apps/usage_tracking/tests/test_logpush_parser.py`

**Interfaces:**
- Consumes: `parse_download_path`, `normalize_country`, `db_integer`, `SURAH_RANGE`
  (download_paths); `status_class_for` (Task 2); `TrafficKind` (Task 1);
  `config.developers_api.developers_api.get_openapi_schema()["paths"]`.
- Produces: `ParsedRequest` (frozen dataclass: `ray_id, occurred_at, kind, asset_id, surah,
  asset_version_id, asset_slug, endpoint, path, country, status_class, bytes, cache_status, ip,
  user_agent, app_slug_raw, client_name, client_version, external_user_id, install_id_raw`),
  `parse_line(line: bytes | str) -> ParsedRequest | None`,
  `parse_lines(lines: Iterable[bytes | str]) -> tuple[list[ParsedRequest], int]` (skipped count).

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_logpush_parser.py
from datetime import UTC, datetime
import json
import re

from apps.usage_tracking.models import TrafficKind, TrafficStatusClass
from apps.usage_tracking.services.logpush_parser import parse_line, parse_lines


def _line(**overrides) -> str:
    record = {
        "RayID": "8f0a1b2c3d4e5f60",
        "EdgeStartTimestamp": "2026-10-18T10:00:18Z",
        "ClientRequestHost": "storage.cms.itqan.dev",
        "ClientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
        "ClientRequestURI": "/media/uploads/assets/13/recitations/091.mp3",
        "EdgeResponseStatus": 206,
        "EdgeResponseBytes": 4096,
        "CacheCacheStatus": "dynamic",
        "ClientIP": "203.0.113.7",
        "ClientCountry": "sa",
        "ClientRequestUserAgent": "Dalvik/2.1.0 (Linux; U; Android 14)",
        "ClientRequestReferer": "",
        "RequestHeaders": {},
    }
    record.update(overrides)
    return json.dumps(record)


class TestParseLine:
    def test_parse_line_where_surah_audio_should_return_audio_request(self):
        # Act
        parsed = parse_line(_line())

        # Assert
        assert parsed is not None
        assert (parsed.kind, parsed.asset_id, parsed.surah) == (TrafficKind.AUDIO_SURAH, 13, 91)
        assert parsed.occurred_at == datetime(2026, 10, 18, 10, 0, 18, tzinfo=UTC)
        assert (parsed.country, parsed.status_class, parsed.bytes) == ("SA", TrafficStatusClass.PARTIAL, 4096)

    def test_parse_line_where_download_param_should_be_gallery_download(self):
        # Arrange
        uri = "/media/uploads/assets/13/versions/7/mushaf.zip?download=mushaf-v1.zip"

        # Act
        parsed = parse_line(_line(ClientRequestURI=uri))

        # Assert
        assert (parsed.kind, parsed.asset_version_id, parsed.path) == (
            TrafficKind.GALLERY_DOWNLOAD,
            7,
            "/media/uploads/assets/13/versions/7/mushaf.zip",
        )

    def test_parse_line_where_app_tag_and_headers_present_should_keep_them(self):
        # Arrange
        headers = {"x-client-name": "quran-companion", "x-client-version": "2.4.1", "x-external-user-id": "u-1"}

        # Act
        parsed = parse_line(
            _line(ClientRequestURI="/media/uploads/assets/13/recitations/091.mp3?c=quran-companion", RequestHeaders=headers)
        )

        # Assert
        assert (parsed.app_slug_raw, parsed.client_name, parsed.client_version, parsed.external_user_id) == (
            "quran-companion",
            "quran-companion",
            "2.4.1",
            "u-1",
        )

    def test_parse_line_where_api_route_with_asset_should_return_api_call(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/recitations/13/2/range/?from=1", EdgeResponseStatus=200))

        # Assert
        assert (parsed.kind, parsed.asset_id, parsed.surah, parsed.endpoint) == (
            TrafficKind.API_CALL,
            13,
            2,
            "/recitations/{asset_id}/{surah_number}/range/",
        )

    def test_parse_line_where_resolve_manifest_should_match_literal_route(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/resolve/manifest/"))

        # Assert
        assert (parsed.endpoint, parsed.asset_slug) == ("/packages/resolve/manifest/", "")

    def test_parse_line_where_resolve_slug_should_keep_slug(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/resolve/hafs-mushaf/"))

        # Assert
        assert (parsed.endpoint, parsed.asset_slug) == ("/packages/resolve/{slug}/", "hafs-mushaf")

    def test_parse_line_where_package_download_should_keep_version(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/packages/download/42/hafs-ar-1.0.0.csv/"))

        # Assert
        assert (parsed.kind, parsed.asset_version_id) == (TrafficKind.API_CALL, 42)

    def test_parse_line_where_oauth_or_portal_or_scanner_path_should_skip(self):
        # Act / Assert
        for uri in ("/token/", "/portal/usage/downloads/summary/", "/.env", "/cms-api/assets/1/"):
            assert parse_line(_line(ClientRequestURI=uri)) is None

    def test_parse_line_where_timestamp_is_unixnano_should_convert(self):
        # Act
        parsed = parse_line(_line(EdgeStartTimestamp=1760781618000000000))

        # Assert
        assert parsed.occurred_at == datetime(2025, 10, 18, 10, 0, 18, tzinfo=UTC)

    def test_parse_line_where_not_json_or_missing_ray_should_skip(self):
        # Act / Assert
        assert parse_line(b"{not json") is None
        assert parse_line(_line(RayID="")) is None

    def test_parse_line_where_install_header_present_should_keep_raw_install_id(self):
        # Act
        parsed = parse_line(_line(RequestHeaders={"x-itqan-install-id": "0b1c"}))

        # Assert
        assert parsed.install_id_raw == "0b1c"


class TestParseLines:
    def test_parse_lines_where_mixed_lines_should_count_skipped(self):
        # Act
        parsed, skipped = parse_lines([_line(), "garbage", _line(ClientRequestURI="/.env")])

        # Assert
        assert (len(parsed), skipped) == (1, 2)


class TestRouteCoverage:
    def test_parse_line_where_any_public_route_should_map_to_its_template(self):
        # Arrange
        from config.developers_api import developers_api

        templates = [p for p in developers_api.get_openapi_schema()["paths"] if p not in ("/token/", "/revoke/")]

        # Act / Assert
        for template in templates:
            path = re.sub(r"\{[^}]+\}", "7", template)
            parsed = parse_line(_line(ClientRequestURI=path))
            assert parsed is not None, template
            assert parsed.endpoint == template
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_logpush_parser.py`
Expected: FAIL — `ModuleNotFoundError: ... logpush_parser`.

- [ ] **Step 3: Rename the two helpers in `download_paths.py`**

Replace `_db_integer` with `db_integer` (definition and its 3 uses) and `_SURAH_RANGE` with
`SURAH_RANGE` (definition and its use). No behaviour change.

- [ ] **Step 4: Implement the parser**

```python
# apps/usage_tracking/services/logpush_parser.py
"""Turns Cloudflare Logpush `http_requests` lines into parsed asset requests.

Kept: asset files under /media/uploads/assets/ and public developer-API routes (taken from the
API's own OpenAPI schema, so new routes are covered automatically). Dropped: everything else on
the hosts (portal, CMS API, OAuth, static files, scanners).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import functools
import json
import re
from urllib.parse import parse_qs

from apps.usage_tracking.models import AssetDownloadFileKind, TrafficKind
from apps.usage_tracking.services.download_paths import SURAH_RANGE, db_integer, normalize_country, parse_download_path
from apps.usage_tracking.services.traffic_classify import status_class_for

_FILE_KINDS = {
    AssetDownloadFileKind.SURAH: TrafficKind.AUDIO_SURAH,
    AssetDownloadFileKind.AYAH: TrafficKind.AUDIO_AYAH,
    AssetDownloadFileKind.VERSION: TrafficKind.VERSION_FILE,
}
# OAuth endpoints share the developer API but are not data access.
_EXCLUDED_API_PATHS = frozenset({"/token/", "/revoke/"})
# Epoch values above this are unixnano (Logpush default); below are seconds.
_NANOSECOND_THRESHOLD = 10**11


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    ray_id: str
    occurred_at: datetime
    kind: str
    asset_id: int | None
    surah: int | None
    asset_version_id: int | None
    asset_slug: str
    endpoint: str
    path: str
    country: str
    status_class: str
    bytes: int
    cache_status: str
    ip: str
    user_agent: str
    app_slug_raw: str
    client_name: str
    client_version: str
    external_user_id: str
    install_id_raw: str


@dataclass(frozen=True, slots=True)
class _Route:
    template: str
    pattern: re.Pattern[str]


@functools.cache
def _api_routes() -> tuple[_Route, ...]:
    """Public developer-API routes; literal routes before parameterised ones."""
    from config.developers_api import developers_api  # lazy: loading every public router is not free

    routes = []
    for template in developers_api.get_openapi_schema()["paths"]:
        if template in _EXCLUDED_API_PATHS:
            continue
        regex = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(template))
        routes.append(_Route(template, re.compile(f"^{regex}$")))
    return tuple(sorted(routes, key=lambda route: (route.pattern.groups, -len(route.template))))


_Located = tuple[str, int | None, int | None, int | None, str, str]


def _locate(path: str, params: dict[str, list[str]]) -> _Located | None:
    if file := parse_download_path(path):
        kind = TrafficKind.GALLERY_DOWNLOAD if "download" in params else _FILE_KINDS[file.file_kind]
        return kind, file.asset_id, file.surah, file.asset_version_id, "", ""
    for route in _api_routes():
        if match := route.pattern.match(path):
            values = match.groupdict()
            surah = db_integer(values.get("surah_number", ""))
            return (
                TrafficKind.API_CALL,
                db_integer(values.get("asset_id", "")),
                surah if surah in SURAH_RANGE else None,
                db_integer(values.get("asset_version_id", "")),
                values.get("slug", "")[:100],
                route.template,
            )
    return None


def _timestamp(value: object) -> datetime:
    if isinstance(value, str) and not value.isdigit():
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    number = int(value)  # type: ignore[call-overload]
    return datetime.fromtimestamp(number / 1e9 if number > _NANOSECOND_THRESHOLD else number, tz=UTC)


def _first(params: dict[str, list[str]], name: str) -> str:
    return (params.get(name) or [""])[0]


def parse_line(line: bytes | str) -> ParsedRequest | None:
    """The request a Logpush line describes, or None when it is malformed or not counted."""
    try:
        record = json.loads(line)
        if not isinstance(record, dict) or not record.get("RayID"):
            return None
        uri = record.get("ClientRequestURI") or record.get("ClientRequestPath") or ""
        path, _, query = uri.partition("?")
        params = parse_qs(query, keep_blank_values=True)
        located = _locate(path, params)
        if located is None:
            return None
        kind, asset_id, surah, version_id, slug, endpoint = located
        headers = record.get("RequestHeaders") or {}
        return ParsedRequest(
            ray_id=str(record["RayID"])[:64],
            occurred_at=_timestamp(record["EdgeStartTimestamp"]),
            kind=kind,
            asset_id=asset_id,
            surah=surah,
            asset_version_id=version_id,
            asset_slug=slug,
            endpoint=endpoint,
            path=path[:512],
            country=normalize_country(record.get("ClientCountry")),
            status_class=status_class_for(int(record.get("EdgeResponseStatus") or 0)),
            bytes=int(record.get("EdgeResponseBytes") or 0),
            cache_status=str(record.get("CacheCacheStatus") or "")[:16],
            ip=str(record.get("ClientIP") or ""),
            user_agent=str(record.get("ClientRequestUserAgent") or ""),
            app_slug_raw=_first(params, "c")[:64],
            client_name=str(headers.get("x-client-name") or "")[:64],
            client_version=str(headers.get("x-client-version") or "")[:32],
            external_user_id=str(headers.get("x-external-user-id") or "")[:64],
            install_id_raw=str(headers.get("x-itqan-install-id") or "")[:64],
        )
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None


def parse_lines(lines: Iterable[bytes | str]) -> tuple[list[ParsedRequest], int]:
    parsed: list[ParsedRequest] = []
    skipped = 0
    for line in lines:
        request = parse_line(line)
        if request is None:
            skipped += 1
        else:
            parsed.append(request)
    return parsed, skipped
```

- [ ] **Step 5: Run the parser tests and the download-path tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_logpush_parser.py apps/usage_tracking/tests/test_download_paths.py`
Expected: all passed. (The unixnano test value 1760781618 s is 2025-10-18 10:00:18 UTC.)

- [ ] **Step 6: Checkpoint** — no commit.

---

### Task 5: Traffic repository (storage, hour/day rebuild, monthly uniques, locks, state)

**Files:**
- Create: `apps/usage_tracking/repositories/traffic.py`
- Test: `apps/usage_tracking/tests/test_traffic_repository.py`

**Interfaces:**
- Consumes: Task 1 models/constants; `apps.content.models.Asset` (table name for the publisher
  join).
- Produces: `TrafficRepository` with
  `imported_keys(keys: Iterable[str]) -> set[str]`,
  `store_file(key: str, events: list[TrafficEvent], error: str = "") -> None`,
  `rebuild_hour(hour: datetime, play_window: timedelta) -> None` (also rebuilds that UTC day),
  `rebuild_month_uniques(month: date) -> None`,
  `purge_events_before(cutoff: datetime) -> int`,
  `edge_requests_by_object(hour: datetime) -> dict[str, int]` (keys are request paths),
  `replace_r2_reads(hour: datetime, rows: list[R2ObjectReadsHourly]) -> None`,
  `try_lock(job: str) -> bool`, `unlock(job: str) -> None`,
  `get_watermark(key: str) -> datetime | None`, `set_watermark(key: str, value: datetime) -> None`,
  `record_run(key: str, now: datetime, error: str) -> None`;
  constants `LOGPUSH_JOB = "logpush"`, `R2_RECONCILIATION_JOB = "r2_reconciliation"`,
  `MAINTENANCE_JOB = "maintenance"`; helper `floor_hour(value: datetime) -> datetime`.

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_traffic_repository.py
from datetime import UTC, date, datetime, timedelta

from model_bakery import baker

from apps.content.models import Asset, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import (
    LogFileImport,
    R2ObjectReadsHourly,
    TrafficChannel,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficMonthlyUniques,
    TrafficPlatform,
    TrafficStatusClass,
    UniqueMeasure,
    UniqueScope,
)
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository

H10 = datetime(2026, 10, 18, 10, tzinfo=UTC)
H11 = H10 + timedelta(hours=1)
WINDOW = timedelta(minutes=5)
FULL = TrafficStatusClass.FULL
PARTIAL = TrafficStatusClass.PARTIAL


def _event(ray: str, at: datetime, **overrides) -> TrafficEvent:
    values = {
        "ray_id": ray,
        "occurred_at": at,
        "kind": TrafficKind.AUDIO_SURAH,
        "asset_id": 13,
        "surah": 91,
        "country": "SA",
        "channel": TrafficChannel.APP_UNIDENTIFIED,
        "platform": TrafficPlatform.ANDROID,
        "status_class": FULL,
        "bytes": 100,
        "listener_id": "a" * 64,
        "ua_family": "dalvik",
        "path": "/media/uploads/assets/13/recitations/091.mp3",
    }
    values.update(overrides)
    return TrafficEvent(**values)


class TestStoreAndRebuild(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()

    def _store(self, *events: TrafficEvent, key: str = "http/production/20261018/a.log.gz") -> None:
        self.repo.store_file(key, list(events))

    def test_store_file_where_same_ray_stored_twice_should_keep_one_event(self):
        # Arrange
        self._store(_event("r1", H10), key="k1")

        # Act
        self._store(_event("r1", H10), key="k2")

        # Assert
        assert TrafficEvent.objects.count() == 1
        assert self.repo.imported_keys(["k1", "k2", "k3"]) == {"k1", "k2"}

    def test_store_file_where_error_given_should_record_file_without_rows(self):
        # Act
        self.repo.store_file("bad.log.gz", [], error="EOFError")

        # Assert
        assert LogFileImport.objects.get(key="bad.log.gz").error == "EOFError"

    def test_rebuild_hour_where_200_and_206_pair_should_count_one_play(self):
        # Arrange
        self._store(_event("r1", H10 + timedelta(seconds=1)), _event("r2", H10 + timedelta(seconds=2), status_class=PARTIAL))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        rows = TrafficHourly.objects.filter(hour=H10)
        assert sum(r.requests for r in rows) == 2
        assert sum(r.sessions for r in rows) == 1
        assert sum(r.bytes for r in rows) == 200

    def test_rebuild_hour_where_gap_over_window_should_count_two_plays(self):
        # Arrange
        self._store(_event("r1", H10), _event("r2", H10 + timedelta(minutes=7)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 2

    def test_rebuild_hour_where_play_continues_from_previous_hour_should_not_recount(self):
        # Arrange
        self._store(_event("r1", H11 - timedelta(minutes=2)), _event("r2", H11 + timedelta(minutes=1)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 1
        assert TrafficHourly.objects.get(hour=H11).sessions == 0

    def test_rebuild_hour_where_bot_or_error_should_not_count(self):
        # Arrange
        self._store(
            _event("bot", H10, is_bot=True),
            _event("404", H10, listener_id="b" * 64, status_class=TrafficStatusClass.CLIENT_ERROR),
        )

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        assert not TrafficHourly.objects.filter(hour=H10).exists()

    def test_rebuild_hour_where_api_calls_should_count_each_call_as_session(self):
        # Arrange
        api = {"kind": TrafficKind.API_CALL, "surah": None, "path": "/recitations/13/", "endpoint": "/recitations/{asset_id}/"}
        self._store(_event("a1", H10, **api), _event("a2", H10 + timedelta(seconds=5), **api))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        row = TrafficHourly.objects.get(hour=H10)
        assert (row.requests, row.sessions, row.endpoint) == (2, 2, "/recitations/{asset_id}/")

    def test_rebuild_hour_where_install_repeats_same_day_should_count_once(self):
        # Arrange
        cli = {"kind": TrafficKind.CLI_INSTALL, "surah": None, "asset_version_id": 7, "install_id": "i" * 64,
               "channel": TrafficChannel.CLI, "platform": TrafficPlatform.DESKTOP}
        self._store(_event("c1", H10, **cli), _event("c2", H11, **cli))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        assert TrafficHourly.objects.get(hour=H10).sessions == 1
        assert TrafficHourly.objects.get(hour=H11).sessions == 0

    def test_rebuild_hour_where_run_twice_should_replace_not_add(self):
        # Arrange
        self._store(_event("r1", H10))
        self.repo.rebuild_hour(H10, WINDOW)
        self._store(_event("r2", H10 + timedelta(minutes=30)), key="k2")

        # Act
        self.repo.rebuild_hour(H10, WINDOW)

        # Assert
        row = TrafficHourly.objects.get(hour=H10)
        assert (row.requests, row.sessions) == (2, 2)

    def test_rebuild_hour_where_hours_rebuilt_should_keep_daily_as_sum(self):
        # Arrange
        self._store(_event("r1", H10), _event("r2", H11 + timedelta(minutes=30)))

        # Act
        self.repo.rebuild_hour(H10, WINDOW)
        self.repo.rebuild_hour(H11, WINDOW)

        # Assert
        daily = TrafficDaily.objects.get(day=date(2026, 10, 18))
        assert (daily.requests, daily.sessions, daily.bytes) == (2, 2, 200)


class TestMonthlyUniques(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()
        self.publisher = baker.make(Publisher, name="Pub")
        self.asset = baker.make(Asset, publisher=self.publisher, name="A", category=CategoryChoice.MUSHAF)

    def test_rebuild_month_uniques_where_listeners_repeat_should_count_distinct_per_scope(self):
        # Arrange
        self.repo.store_file(
            "k",
            [
                _event("r1", H10, asset_id=self.asset.id),
                _event("r2", H10 + timedelta(days=3), asset_id=self.asset.id),
                _event("r3", H10, asset_id=self.asset.id, listener_id="b" * 64),
            ],
        )

        # Act
        self.repo.rebuild_month_uniques(date(2026, 10, 1))

        # Assert
        counts = {
            (row.scope, row.scope_id): row.count
            for row in TrafficMonthlyUniques.objects.filter(measure=UniqueMeasure.LISTENERS)
        }
        assert counts == {
            (UniqueScope.ALL, 0): 2,
            (UniqueScope.ASSET, self.asset.id): 2,
            (UniqueScope.PUBLISHER, self.publisher.id): 2,
        }


class TestMaintenanceHelpers(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = TrafficRepository()

    def test_purge_events_before_where_old_events_should_delete_only_those(self):
        # Arrange
        self.repo.store_file("k", [_event("old", H10), _event("new", H11)])

        # Act
        deleted = self.repo.purge_events_before(H10 + timedelta(minutes=30))

        # Assert
        assert deleted == 1
        assert list(TrafficEvent.objects.values_list("ray_id", flat=True)) == ["new"]

    def test_edge_requests_by_object_where_file_events_should_count_per_path(self):
        # Arrange
        self.repo.store_file("k", [_event("r1", H10), _event("r2", H10, status_class=PARTIAL), _event("r3", H11)])

        # Act
        counts = self.repo.edge_requests_by_object(H10)

        # Assert
        assert counts == {"/media/uploads/assets/13/recitations/091.mp3": 2}

    def test_replace_r2_reads_where_called_twice_should_replace_and_advance_watermark(self):
        # Arrange
        row = {"hour": H10, "object_key": "media/x.mp3", "asset_id": 13, "reads": 5, "edge_requests": 4}
        self.repo.replace_r2_reads(H10, [R2ObjectReadsHourly(**row)])

        # Act
        self.repo.replace_r2_reads(H10, [R2ObjectReadsHourly(**{**row, "reads": 6})])

        # Assert
        assert R2ObjectReadsHourly.objects.get().reads == 6
        assert self.repo.get_watermark("r2_reconciliation") == H11

    def test_record_run_and_lock_where_used_should_store_state_and_release(self):
        # Act
        acquired = self.repo.try_lock(LOGPUSH_JOB)
        self.repo.unlock(LOGPUSH_JOB)
        self.repo.set_watermark(LOGPUSH_JOB, H10)
        self.repo.record_run(LOGPUSH_JOB, H11, "boom")

        # Assert
        assert acquired is True
        assert self.repo.get_watermark(LOGPUSH_JOB) == H10
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_repository.py`
Expected: FAIL — `ModuleNotFoundError: ... repositories.traffic`.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/repositories/traffic.py
"""Persistence for usage reports: traffic events, rollups, monthly uniques and job state."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta

from django.db import connection, transaction
from django.db.models import Count, Sum

from apps.content.models import Asset
from apps.usage_tracking.models import (
    AUDIO_KINDS,
    COUNTED_STATUSES,
    EVENT_COUNTED_KINDS,
    FILE_SESSION_KINDS,
    SESSION_STATUSES,
    TRAFFIC_DIMENSIONS,
    LogFileImport,
    R2ObjectReadsHourly,
    TrafficDaily,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficMonthlyUniques,
    TrafficSource,
    TrafficStatusClass,
    UniqueMeasure,
    UniqueScope,
    UsageImportState,
)

LOGPUSH_JOB = "logpush"
R2_RECONCILIATION_JOB = "r2_reconciliation"
MAINTENANCE_JOB = "maintenance"
# Arbitrary constants identifying each job's Postgres advisory lock.
_LOCK_IDS = {LOGPUSH_JOB: 7_340_212_027, R2_RECONCILIATION_JOB: 7_340_212_028, MAINTENANCE_JOB: 7_340_212_029}
_HOUR = timedelta(hours=1)
_DIMENSION_COLUMNS = ", ".join(TRAFFIC_DIMENSIONS)

DimensionKey = tuple[object, ...]


def floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _month_start(month: date) -> datetime:
    return datetime(month.year, month.month, 1, tzinfo=UTC)


def _next_month(month: date) -> date:
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


# A file-kind request starts a session unless the same listener requested the same file within
# the window before it. The CTE reads `window` of context before the hour so a play that began
# in the previous hour is not counted again.
_FILE_SESSIONS_SQL = f"""
WITH ordered AS (
    SELECT {_DIMENSION_COLUMNS}, occurred_at,
           LAG(occurred_at) OVER (
               PARTITION BY listener_id, asset_id, kind, surah, asset_version_id
               ORDER BY occurred_at, ray_id
           ) AS previous_at
    FROM {{table}}
    WHERE occurred_at >= %(context_start)s AND occurred_at < %(end)s AND NOT is_bot
      AND status_class = ANY(%(statuses)s) AND kind = ANY(%(kinds)s)
)
SELECT {_DIMENSION_COLUMNS}, COUNT(*)
FROM ordered
WHERE occurred_at >= %(start)s AND (previous_at IS NULL OR occurred_at - previous_at > %(window)s)
GROUP BY {_DIMENSION_COLUMNS}
"""  # nosec B608 — only constant identifiers are interpolated

# An install counts once per install id, asset version and UTC day, in the hour of its first event.
# Requests without an install id (opted out) count individually.
_INSTALL_SESSIONS_SQL = f"""
SELECT {_DIMENSION_COLUMNS}, COUNT(*)
FROM (
    SELECT DISTINCT ON (COALESCE(NULLIF(install_id, ''), ray_id), asset_version_id) *
    FROM {{table}}
    WHERE occurred_at >= %(day_start)s AND occurred_at < %(end)s AND NOT is_bot
      AND kind = %(kind)s AND status_class = ANY(%(statuses)s)
    ORDER BY COALESCE(NULLIF(install_id, ''), ray_id), asset_version_id, occurred_at, ray_id
) first_of_day
WHERE occurred_at >= %(start)s
GROUP BY {_DIMENSION_COLUMNS}
"""  # nosec B608 — only constant identifiers are interpolated

_UNIQUES_SQL = """
SELECT {scope} AS scope_id, COUNT(DISTINCT {identity})
FROM {events} e LEFT JOIN {assets} a ON a.id = e.asset_id
WHERE e.occurred_at >= %(start)s AND e.occurred_at < %(end)s AND NOT e.is_bot
  AND e.status_class = ANY(%(statuses)s) AND e.kind = ANY(%(kinds)s)
GROUP BY 1
HAVING {scope} IS NOT NULL
"""  # nosec B608 — only constant identifiers are interpolated

_UNIQUE_SCOPES = {
    UniqueScope.ALL: "0",
    UniqueScope.ASSET: "e.asset_id",
    UniqueScope.PUBLISHER: "a.publisher_id",
    UniqueScope.APP: "e.app_id",
}
_UNIQUE_MEASURES: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    UniqueMeasure.LISTENERS: (AUDIO_KINDS, SESSION_STATUSES, "e.listener_id"),
    UniqueMeasure.DOWNLOADERS: (
        (TrafficKind.VERSION_FILE, TrafficKind.GALLERY_DOWNLOAD),
        SESSION_STATUSES,
        "e.listener_id",
    ),
    UniqueMeasure.INSTALLS: (
        (TrafficKind.CLI_INSTALL,),
        COUNTED_STATUSES,
        "COALESCE(NULLIF(e.install_id, ''), e.ray_id)",
    ),
    UniqueMeasure.END_USERS: ((TrafficKind.API_CALL,), COUNTED_STATUSES, "NULLIF(e.end_user_id, '')"),
}


class TrafficRepository:
    # -- import bookkeeping -------------------------------------------------
    def imported_keys(self, keys: Iterable[str]) -> set[str]:
        return set(LogFileImport.objects.filter(key__in=list(keys)).values_list("key", flat=True))

    def store_file(self, key: str, events: list[TrafficEvent], error: str = "") -> None:
        """Insert a file's events and record the file in one transaction (re-runs never double-count)."""
        with transaction.atomic():
            TrafficEvent.objects.bulk_create(events, ignore_conflicts=True, batch_size=2000)
            LogFileImport.objects.create(key=key, rows=len(events), error=error)

    # -- rollups -------------------------------------------------------------
    def rebuild_hour(self, hour: datetime, play_window: timedelta) -> None:
        """Replace the hour's rollup rows (and its day's) from events, atomically."""
        hour = floor_hour(hour)
        end = hour + _HOUR
        with transaction.atomic():
            metrics: dict[DimensionKey, list[int]] = defaultdict(lambda: [0, 0, 0])
            for row in self._totals(hour, end):
                entry = metrics[tuple(row[dimension] for dimension in TRAFFIC_DIMENSIONS)]
                entry[0] += row["total_requests"]
                entry[1] += row["total_bytes"] or 0
                if row["kind"] in EVENT_COUNTED_KINDS:
                    entry[2] += row["total_requests"]
            for key, sessions in self._sessions(hour, end, play_window).items():
                metrics[key][2] += sessions

            TrafficHourly.objects.filter(hour=hour).delete()
            TrafficHourly.objects.bulk_create(
                [
                    TrafficHourly(
                        hour=hour,
                        **dict(zip(TRAFFIC_DIMENSIONS, key, strict=True)),
                        requests=requests,
                        bytes=bytes_,
                        sessions=sessions,
                    )
                    for key, (requests, bytes_, sessions) in metrics.items()
                ]
            )
            self._rebuild_day(hour.date())

    def _totals(self, start: datetime, end: datetime):
        return (
            TrafficEvent.objects.filter(
                occurred_at__gte=start, occurred_at__lt=end, is_bot=False, status_class__in=COUNTED_STATUSES
            )
            .values(*TRAFFIC_DIMENSIONS)
            .annotate(total_requests=Count("id"), total_bytes=Sum("bytes"))
            .order_by()
        )

    def _sessions(self, hour: datetime, end: datetime, play_window: timedelta) -> dict[DimensionKey, int]:
        table = TrafficEvent._meta.db_table
        sessions: dict[DimensionKey, int] = defaultdict(int)
        with connection.cursor() as cursor:
            cursor.execute(
                _FILE_SESSIONS_SQL.format(table=table),
                {
                    "context_start": hour - play_window,
                    "start": hour,
                    "end": end,
                    "window": play_window,
                    "statuses": list(SESSION_STATUSES),
                    "kinds": list(FILE_SESSION_KINDS),
                },
            )
            for row in cursor.fetchall():
                sessions[tuple(row[:-1])] += int(row[-1])
            cursor.execute(
                _INSTALL_SESSIONS_SQL.format(table=table),
                {
                    "day_start": datetime.combine(hour.date(), time.min, tzinfo=UTC),
                    "start": hour,
                    "end": end,
                    "kind": TrafficKind.CLI_INSTALL.value,
                    "statuses": list(COUNTED_STATUSES),
                },
            )
            for row in cursor.fetchall():
                sessions[tuple(row[:-1])] += int(row[-1])
        return sessions

    def _rebuild_day(self, day: date) -> None:
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        rows = (
            TrafficHourly.objects.filter(hour__gte=day_start, hour__lt=day_start + timedelta(days=1))
            .values(*TRAFFIC_DIMENSIONS)
            .annotate(total_requests=Sum("requests"), total_bytes=Sum("bytes"), total_sessions=Sum("sessions"))
            .order_by()
        )
        TrafficDaily.objects.filter(day=day).delete()
        TrafficDaily.objects.bulk_create(
            [
                TrafficDaily(
                    day=day,
                    **{dimension: row[dimension] for dimension in TRAFFIC_DIMENSIONS},
                    requests=row["total_requests"],
                    bytes=row["total_bytes"],
                    sessions=row["total_sessions"],
                )
                for row in rows
            ]
        )

    def rebuild_month_uniques(self, month: date) -> None:
        start, end = _month_start(month), _month_start(_next_month(month))
        rows: list[TrafficMonthlyUniques] = []
        with connection.cursor() as cursor:
            for measure, (kinds, statuses, identity) in _UNIQUE_MEASURES.items():
                for scope, scope_expr in _UNIQUE_SCOPES.items():
                    sql = _UNIQUES_SQL.format(
                        scope=scope_expr,
                        identity=identity,
                        events=TrafficEvent._meta.db_table,
                        assets=Asset._meta.db_table,
                    )
                    cursor.execute(sql, {"start": start, "end": end, "kinds": list(kinds), "statuses": list(statuses)})
                    rows.extend(
                        TrafficMonthlyUniques(
                            month=start.date(), scope=scope, scope_id=int(scope_id), measure=measure, count=int(count)
                        )
                        for scope_id, count in cursor.fetchall()
                        if count
                    )
        with transaction.atomic():
            TrafficMonthlyUniques.objects.filter(month=start.date()).delete()
            TrafficMonthlyUniques.objects.bulk_create(rows)

    def purge_events_before(self, cutoff: datetime) -> int:
        deleted, _ = TrafficEvent.objects.filter(occurred_at__lt=cutoff).delete()
        return deleted

    # -- reconciliation -------------------------------------------------------
    def edge_requests_by_object(self, hour: datetime) -> dict[str, int]:
        hour = floor_hour(hour)
        rows = (
            TrafficEvent.objects.filter(
                source=TrafficSource.EDGE,
                occurred_at__gte=hour,
                occurred_at__lt=hour + _HOUR,
                kind__in=FILE_SESSION_KINDS,
                status_class__in=(*SESSION_STATUSES, TrafficStatusClass.SUCCESS),
            )
            .values("path")
            .annotate(total=Count("id"))
            .order_by()
        )
        return {row["path"]: row["total"] for row in rows}

    def replace_r2_reads(self, hour: datetime, rows: list[R2ObjectReadsHourly]) -> None:
        hour = floor_hour(hour)
        with transaction.atomic():
            R2ObjectReadsHourly.objects.filter(hour=hour).delete()
            R2ObjectReadsHourly.objects.bulk_create(rows)
            state, _ = UsageImportState.objects.select_for_update().get_or_create(key=R2_RECONCILIATION_JOB)
            if state.watermark is None or hour + _HOUR > state.watermark:
                state.watermark = hour + _HOUR
                state.save(update_fields=["watermark", "updated_at"])

    # -- job state ------------------------------------------------------------
    def try_lock(self, job: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [_LOCK_IDS[job]])
            return bool(cursor.fetchone()[0])

    def unlock(self, job: str) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_LOCK_IDS[job]])

    def get_watermark(self, key: str) -> datetime | None:
        return UsageImportState.objects.filter(key=key).values_list("watermark", flat=True).first()

    def set_watermark(self, key: str, value: datetime) -> None:
        UsageImportState.objects.update_or_create(key=key, defaults={"watermark": value})

    def record_run(self, key: str, now: datetime, error: str) -> None:
        UsageImportState.objects.update_or_create(key=key, defaults={"last_run_at": now, "last_error": error})
```

- [ ] **Step 4: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_repository.py`
Expected: all passed.

- [ ] **Step 5: Checkpoint** — no commit.

---

### Task 6: Logpush importer (R2 client, event building, hourly task)

**Files:**
- Create: `apps/usage_tracking/services/r2_logs_client.py`, `apps/usage_tracking/services/logpush_import.py`
- Modify: `apps/usage_tracking/tasks.py`, `config/celery.py`
- Test: `apps/usage_tracking/tests/test_r2_logs_client.py`, `apps/usage_tracking/tests/test_logpush_import.py`

**Interfaces:**
- Consumes: Task 2 classifiers, Task 3 identities and settings, Task 4 `parse_lines` /
  `ParsedRequest`, Task 5 `TrafficRepository`, `LOGPUSH_JOB`, `floor_hour`;
  `AssetVersion`, `Asset` (content); `settings.CLOUDFLARE_R2_ENDPOINT`,
  `settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES`.
- Produces: `R2LogsClient(endpoint_url, access_key_id, secret_access_key, bucket)` with
  `list_day_prefixes(prefix) -> list[str]`, `list_keys(prefix) -> list[str]`,
  `iter_lines(key) -> Iterator[bytes]`;
  `build_events(parsed: list[ParsedRequest]) -> list[TrafficEvent]`,
  `touched_hours(events: Iterable[TrafficEvent], play_window: timedelta) -> set[datetime]`,
  `import_logpush(now: datetime | None = None) -> ImportResult`
  (`ImportResult(files_imported: int, events: int, skipped_lines: int, error: str)`);
  task `import_logpush_task` (beat: minute 10).

- [ ] **Step 1: Write the failing client tests**

```python
# apps/usage_tracking/tests/test_r2_logs_client.py
import gzip
import io

from botocore.response import StreamingBody
from botocore.stub import Stubber

from apps.usage_tracking.services.r2_logs_client import R2LogsClient


def _client() -> R2LogsClient:
    return R2LogsClient("https://example.r2.cloudflarestorage.com", "id", "secret", "itqan-usage-logs")


class TestR2LogsClient:
    def test_list_day_prefixes_where_pages_returned_should_collect_sorted_prefixes(self):
        # Arrange
        client = _client()
        stubber = Stubber(client._s3)
        stubber.add_response(
            "list_objects_v2",
            {"CommonPrefixes": [{"Prefix": "http/production/20261018/"}], "IsTruncated": True, "NextContinuationToken": "t"},
            {"Bucket": "itqan-usage-logs", "Prefix": "http/production/", "Delimiter": "/"},
        )
        stubber.add_response(
            "list_objects_v2",
            {"CommonPrefixes": [{"Prefix": "http/production/20261017/"}], "IsTruncated": False},
            {"Bucket": "itqan-usage-logs", "Prefix": "http/production/", "Delimiter": "/", "ContinuationToken": "t"},
        )

        # Act
        with stubber:
            prefixes = client.list_day_prefixes("http/production/")

        # Assert
        assert prefixes == ["http/production/20261017/", "http/production/20261018/"]

    def test_iter_lines_where_gzip_object_should_yield_non_empty_lines(self):
        # Arrange
        client = _client()
        payload = gzip.compress(b'{"a":1}\n\n{"b":2}\n')
        stubber = Stubber(client._s3)
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(payload), len(payload))},
            {"Bucket": "itqan-usage-logs", "Key": "k.log.gz"},
        )

        # Act
        with stubber:
            lines = list(client.iter_lines("k.log.gz"))

        # Assert
        assert lines == [b'{"a":1}\n', b'{"b":2}\n']
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_r2_logs_client.py`
Expected: FAIL — `ModuleNotFoundError: ... r2_logs_client`.

- [ ] **Step 3: Implement the client**

```python
# apps/usage_tracking/services/r2_logs_client.py
"""Reads Cloudflare Logpush files from the R2 logs bucket (S3 API, read-only key)."""

from collections.abc import Iterator
import gzip

import boto3


class R2LogsClient:
    def __init__(self, endpoint_url: str, access_key_id: str, secret_access_key: str, bucket: str) -> None:
        self._bucket = bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def _pages(self, **kwargs) -> Iterator[dict]:
        token = None
        while True:
            params = {"Bucket": self._bucket, **kwargs}
            if token:
                params["ContinuationToken"] = token
            page = self._s3.list_objects_v2(**params)
            yield page
            if not page.get("IsTruncated"):
                return
            token = page["NextContinuationToken"]

    def list_day_prefixes(self, prefix: str) -> list[str]:
        """The `<prefix><YYYYMMDD>/` folders Logpush created, oldest first."""
        prefixes = [entry["Prefix"] for page in self._pages(Prefix=prefix, Delimiter="/") for entry in page.get("CommonPrefixes", [])]
        return sorted(prefixes)

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(entry["Key"] for page in self._pages(Prefix=prefix) for entry in page.get("Contents", []))

    def iter_lines(self, key: str) -> Iterator[bytes]:
        body = self._s3.get_object(Bucket=self._bucket, Key=key)["Body"]
        stream = gzip.GzipFile(fileobj=body) if key.endswith(".gz") else body
        try:
            for line in stream:
                if line.strip():
                    yield line
        finally:
            body.close()
```

- [ ] **Step 4: Run the client tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_r2_logs_client.py`
Expected: 2 passed.

- [ ] **Step 5: Write the failing importer tests**

```python
# apps/usage_tracking/tests/test_logpush_import.py
from datetime import UTC, datetime, timedelta
import gzip
import json
from unittest.mock import MagicMock, patch

from django.test import override_settings
from model_bakery import baker
import pytest

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    LogFileImport,
    TrafficChannel,
    TrafficEvent,
    TrafficHourly,
    TrafficKind,
    TrafficPlatform,
)
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository
from apps.usage_tracking.services import logpush_import
from apps.usage_tracking.services.logpush_import import build_events, import_logpush, touched_hours
from apps.usage_tracking.services.logpush_parser import parse_line
from apps.usage_tracking.services.r2_logs_client import R2LogsClient

NOW = datetime(2026, 10, 18, 12, 10, tzinfo=UTC)
PREFIX = "http/production/"


def _line(ray: str, at: str = "2026-10-18T10:05:00Z", **overrides) -> bytes:
    record = {
        "RayID": ray,
        "EdgeStartTimestamp": at,
        "ClientRequestURI": "/media/uploads/assets/13/recitations/091.mp3",
        "EdgeResponseStatus": 200,
        "EdgeResponseBytes": 100,
        "CacheCacheStatus": "dynamic",
        "ClientIP": "203.0.113.7",
        "ClientCountry": "sa",
        "ClientRequestUserAgent": "Dalvik/2.1.0 (Linux; U; Android 14)",
        "RequestHeaders": {},
    }
    record.update(overrides)
    return json.dumps(record).encode() + b"\n"


_SETTINGS = {
    "ENABLE_USAGE_LOGPUSH_IMPORT": True,
    "USAGE_LOGS_PREFIX": PREFIX,
    "USAGE_LOGS_ACCESS_KEY_ID": "id",
    "USAGE_LOGS_SECRET_ACCESS_KEY": "secret",
    "CLOUDFLARE_R2_ENDPOINT": "https://example.r2.cloudflarestorage.com",
    "USAGE_IDENTITY_KEY": "identity",
    "ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES": 5,
    "USAGE_LOGPUSH_MAX_FILES_PER_RUN": 500,
}


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestBuildEvents(BaseTestCase):
    def test_build_events_where_android_audio_should_classify_and_hash(self):
        # Act
        [event] = build_events([parse_line(_line("r1"))])

        # Assert
        assert (event.kind, event.channel, event.platform, event.ua_family) == (
            TrafficKind.AUDIO_SURAH,
            TrafficChannel.APP_UNIDENTIFIED,
            TrafficPlatform.ANDROID,
            "dalvik",
        )
        assert len(event.listener_id) == 64
        assert "203.0.113.7" not in event.listener_id

    def test_build_events_where_version_file_should_resolve_asset_language(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        version = baker.make(AssetVersion, asset=asset)
        uri = f"/media/uploads/assets/{asset.id}/versions/{version.id}/file.zip"

        # Act
        [event] = build_events([parse_line(_line("v1", ClientRequestURI=uri))])

        # Assert
        assert (event.kind, event.asset_id, event.asset_version_id) == (TrafficKind.VERSION_FILE, asset.id, version.id)
        assert event.language == version.asset_language.language

    def test_build_events_where_resolve_slug_should_resolve_asset(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF, slug="hafs-mushaf")

        # Act
        [event] = build_events([parse_line(_line("s1", ClientRequestURI="/packages/resolve/hafs-mushaf/"))])

        # Assert
        assert event.asset_id == asset.id

    def test_build_events_where_cli_install_header_should_hash_install_and_mark_cli(self):
        # Act
        [event] = build_events([parse_line(_line("c1", RequestHeaders={"x-itqan-install-id": "u"}))])

        # Assert
        assert (event.channel, len(event.install_id)) == (TrafficChannel.CLI, 64)

    def test_touched_hours_where_event_near_hour_end_should_include_next_hour(self):
        # Arrange
        events = build_events([parse_line(_line("r1", at="2026-10-18T10:57:00Z"))])

        # Act
        hours = touched_hours(events, timedelta(minutes=5))

        # Assert
        assert hours == {datetime(2026, 10, 18, 10, tzinfo=UTC), datetime(2026, 10, 18, 11, tzinfo=UTC)}


@override_settings(**_SETTINGS)
class TestImportLogpush(BaseTestCase):
    def _patch_client(self, files: dict[str, bytes]):
        client = MagicMock(spec=R2LogsClient)
        client.list_day_prefixes.return_value = sorted({key[: len(PREFIX) + 9] for key in files})
        client.list_keys.side_effect = lambda prefix: sorted(k for k in files if k.startswith(prefix))

        def iter_lines(key: str):
            yield from gzip.decompress(files[key]).splitlines(keepends=True)

        client.iter_lines.side_effect = iter_lines
        return patch.object(logpush_import, logpush_import._build_client.__name__, return_value=client)

    def test_import_logpush_where_disabled_should_do_nothing(self):
        # Arrange
        with self.settings(ENABLE_USAGE_LOGPUSH_IMPORT=False):
            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        assert not LogFileImport.objects.exists()

    def test_import_logpush_where_new_files_should_store_events_and_rebuild_hours(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1") + b"garbage\n" + _line("r2", ClientRequestURI="/.env"))}

        # Act
        with self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert (result.files_imported, result.events, result.skipped_lines, result.error) == (1, 1, 2, "")
        assert TrafficHourly.objects.get(hour=datetime(2026, 10, 18, 10, tzinfo=UTC)).sessions == 1
        assert TrafficRepository().get_watermark(LOGPUSH_JOB) == datetime(2026, 10, 18, tzinfo=UTC)

    def test_import_logpush_where_rerun_should_skip_imported_files(self):
        # Arrange
        files = {f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))}
        with self._patch_client(files):
            import_logpush(NOW)

            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        assert TrafficEvent.objects.count() == 1

    def test_import_logpush_where_file_corrupt_should_record_error_and_continue(self):
        # Arrange
        files = {
            f"{PREFIX}20261018/a.log.gz": gzip.compress(_line("r1"))[:20],
            f"{PREFIX}20261018/b.log.gz": gzip.compress(_line("r2")),
        }

        # Act
        with self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 2
        assert LogFileImport.objects.get(key=f"{PREFIX}20261018/a.log.gz").error != ""
        assert list(TrafficEvent.objects.values_list("ray_id", flat=True)) == ["r2"]

    def test_import_logpush_where_batch_limit_reached_should_keep_watermark_at_pending_day(self):
        # Arrange
        files = {
            f"{PREFIX}20261017/a.log.gz": gzip.compress(_line("r1", at="2026-10-17T10:00:00Z")),
            f"{PREFIX}20261018/b.log.gz": gzip.compress(_line("r2")),
        }

        # Act
        with self.settings(USAGE_LOGPUSH_MAX_FILES_PER_RUN=1), self._patch_client(files):
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 1
        assert TrafficRepository().get_watermark(LOGPUSH_JOB) == datetime(2026, 10, 18, tzinfo=UTC)

    def test_import_logpush_where_lock_held_should_skip(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.try_lock.__name__, return_value=False),
            self._patch_client({}) as build_client,
        ):
            # Act
            result = import_logpush(NOW)

        # Assert
        assert result.files_imported == 0
        build_client.assert_not_called()

    def test_import_logpush_where_record_run_fails_should_still_unlock(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.record_run.__name__, side_effect=RuntimeError("db")),
            patch.object(TrafficRepository, TrafficRepository.unlock.__name__) as unlock,
            self._patch_client({}),
            pytest.raises(RuntimeError),
        ):
            # Act
            import_logpush(NOW)

        # Assert
        unlock.assert_called_once()
```

- [ ] **Step 6: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_logpush_import.py`
Expected: FAIL — `ModuleNotFoundError: ... logpush_import`.

- [ ] **Step 7: Implement the importer**

```python
# apps/usage_tracking/services/logpush_import.py
"""Hourly import of Cloudflare Logpush files (every edge request) from R2 into traffic events.

Files are listed per day folder and skipped once recorded in `LogFileImport`, so missed runs
catch up and re-runs never double-count. Every hour that received events is then rebuilt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import logging
import zlib

from django.conf import settings

from apps.content.models import Asset, AssetVersion
from apps.usage_tracking.models import TrafficEvent, TrafficKind, TrafficSource
from apps.usage_tracking.repositories.traffic import LOGPUSH_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.logpush_parser import ParsedRequest, parse_lines
from apps.usage_tracking.services.r2_logs_client import R2LogsClient
from apps.usage_tracking.services.traffic_classify import channel_for, is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import end_user_id_for, install_id_for, listener_id_for

logger = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
# Folders older than the watermark day minus this are assumed complete.
_RELIST_DAYS = 1
# Logpush pushes every few minutes; a day folder with nothing newer than this means it stopped.
_STALE_DAYS = 1


@dataclass(frozen=True, slots=True)
class ImportResult:
    files_imported: int
    events: int
    skipped_lines: int
    error: str


class _Resolver:
    """Batch lookups for asset ids and languages the request path does not carry."""

    def __init__(self, parsed: list[ParsedRequest]) -> None:
        version_ids = {p.asset_version_id for p in parsed if p.asset_version_id}
        slugs = {p.asset_slug for p in parsed if p.asset_slug}
        self._versions = {
            row["id"]: (row["asset_id"], row["asset_language__language"] or "")
            for row in AssetVersion.objects.filter(id__in=version_ids).values(
                "id", "asset_id", "asset_language__language"
            )
        }
        self._slugs = dict(Asset.objects.filter(slug__in=slugs).values_list("slug", "id"))

    def asset_id(self, parsed: ParsedRequest) -> int | None:
        if parsed.asset_id is not None:
            return parsed.asset_id
        if parsed.asset_version_id in self._versions:
            return self._versions[parsed.asset_version_id][0]
        return self._slugs.get(parsed.asset_slug)

    def language(self, parsed: ParsedRequest) -> str:
        return self._versions.get(parsed.asset_version_id, (None, ""))[1]


def build_events(parsed: list[ParsedRequest]) -> list[TrafficEvent]:
    resolver = _Resolver(parsed)
    events: list[TrafficEvent] = []
    missing_ip = 0
    for request in parsed:
        family = ua_family(request.user_agent)
        if not request.ip:
            missing_ip += 1
        events.append(
            TrafficEvent(
                ray_id=request.ray_id,
                occurred_at=request.occurred_at,
                source=TrafficSource.EDGE,
                kind=request.kind,
                asset_id=resolver.asset_id(request),
                surah=request.surah,
                asset_version_id=request.asset_version_id,
                language=resolver.language(request),
                country=request.country,
                channel=channel_for(request.kind, family, has_install_id=bool(request.install_id_raw)),
                platform=platform_for(request.user_agent, family),
                app_id=None,
                endpoint=request.endpoint,
                path=request.path,
                app_slug_raw=request.app_slug_raw,
                status_class=request.status_class,
                bytes=request.bytes,
                cache_status=request.cache_status,
                listener_id=listener_id_for(request.ip, request.user_agent, request.ray_id),
                end_user_id=end_user_id_for(request.client_name, request.external_user_id),
                install_id=install_id_for(request.install_id_raw),
                ua_family=family,
                client_name=request.client_name,
                client_version=request.client_version,
                is_bot=is_bot_user_agent(request.user_agent),
            )
        )
    if missing_ip:
        logger.warning("import_logpush: %d request(s) without ClientIP; each counts as its own listener", missing_ip)
    return events


def touched_hours(events: Iterable[TrafficEvent], play_window: timedelta) -> set[datetime]:
    """Hours whose rollups change when these events are added."""
    hours: set[datetime] = set()
    for event in events:
        hour = floor_hour(event.occurred_at)
        hours.add(hour)
        if event.kind == TrafficKind.CLI_INSTALL:
            # An earlier install moves "first of the day" out of later hours of the same day.
            day_end = datetime.combine(hour.date() + timedelta(days=1), time.min, tzinfo=UTC)
            next_hour = hour + _HOUR
            while next_hour < day_end:
                hours.add(next_hour)
                next_hour += _HOUR
        elif event.occurred_at >= hour + _HOUR - play_window:
            hours.add(hour + _HOUR)  # a play may continue into the next hour
    return hours


def _build_client() -> R2LogsClient:
    return R2LogsClient(
        endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT,
        access_key_id=settings.USAGE_LOGS_ACCESS_KEY_ID,
        secret_access_key=settings.USAGE_LOGS_SECRET_ACCESS_KEY,
        bucket=settings.USAGE_LOGS_BUCKET,
    )


def _folder_day(key: str) -> date:
    """`<prefix>YYYYMMDD/...` → that date."""
    return datetime.strptime(key[len(settings.USAGE_LOGS_PREFIX) :][:8], "%Y%m%d").date()


def _pending_keys(client: R2LogsClient, repo: TrafficRepository, watermark: datetime | None) -> tuple[list[str], list[str]]:
    folders = client.list_day_prefixes(settings.USAGE_LOGS_PREFIX)
    if watermark is not None:
        oldest = watermark.date() - timedelta(days=_RELIST_DAYS)
        folders = [folder for folder in folders if _folder_day(folder) >= oldest]
    pending: list[str] = []
    for folder in folders:
        keys = client.list_keys(folder)
        done = repo.imported_keys(keys)
        pending.extend(key for key in keys if key not in done)
    return folders, pending


def import_logpush(now: datetime | None = None) -> ImportResult:
    if not settings.ENABLE_USAGE_LOGPUSH_IMPORT:
        logger.info("import_logpush: disabled via ENABLE_USAGE_LOGPUSH_IMPORT; skipping")
        return ImportResult(0, 0, 0, "")
    if not (settings.USAGE_LOGS_ACCESS_KEY_ID and settings.USAGE_LOGS_SECRET_ACCESS_KEY and settings.CLOUDFLARE_R2_ENDPOINT):
        logger.warning("import_logpush: missing USAGE_LOGS_* credentials or CLOUDFLARE_R2_ENDPOINT; skipping")
        return ImportResult(0, 0, 0, "")

    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(LOGPUSH_JOB):
        logger.info("import_logpush: another run holds the lock; skipping")
        return ImportResult(0, 0, 0, "")

    files = events_total = skipped_total = 0
    error = ""
    play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
    try:
        client = _build_client()
        folders, pending = _pending_keys(client, repo, repo.get_watermark(LOGPUSH_JOB))
        batch = pending[: settings.USAGE_LOGPUSH_MAX_FILES_PER_RUN]
        hours: set[datetime] = set()
        for key in batch:
            try:
                parsed, skipped = parse_lines(client.iter_lines(key))
            except (OSError, EOFError, zlib.error) as exc:  # truncated or non-gzip file
                logger.error("import_logpush: unreadable file %s: %s", key, exc)
                repo.store_file(key, [], error=f"{type(exc).__name__}: {exc}")
                files += 1
                continue
            events = build_events(parsed)
            repo.store_file(key, events)
            hours |= touched_hours(events, play_window)
            files += 1
            events_total += len(events)
            skipped_total += skipped
        for hour in sorted(hours):
            repo.rebuild_hour(hour, play_window)

        remaining = pending[len(batch) :]
        if remaining:
            watermark_day = _folder_day(remaining[0])
        elif folders:
            watermark_day = _folder_day(folders[-1])
        else:
            watermark_day = None
        if watermark_day is not None:
            repo.set_watermark(LOGPUSH_JOB, datetime.combine(watermark_day, time.min, tzinfo=UTC))
        if not folders or _folder_day(folders[-1]) < now.date() - timedelta(days=_STALE_DAYS):
            logger.error("import_logpush: no recent Logpush files under %s (check the Logpush job)", settings.USAGE_LOGS_PREFIX)
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("import_logpush: run failed after %d file(s)", files)
    finally:
        try:
            repo.record_run(LOGPUSH_JOB, now, error)
        finally:
            repo.unlock(LOGPUSH_JOB)

    logger.info("import_logpush: files=%d events=%d skipped_lines=%d", files, events_total, skipped_total)
    return ImportResult(files, events_total, skipped_total, error)
```

Note: `client.iter_lines` is a generator; `parse_lines` consumes it inside the `try`, so a gzip
error raised mid-file is caught there and nothing from that file is stored.

- [ ] **Step 8: Add the task and beat entry**

In `apps/usage_tracking/tasks.py` add the import
`from apps.usage_tracking.services.logpush_import import import_logpush` and:

```python
@shared_task(acks_late=True, soft_time_limit=1500, time_limit=1560, ignore_result=True)
def import_logpush_task() -> None:
    """Import new Cloudflare Logpush files (see `logpush_import`).

    No autoretry: unimported files stay pending and the next hourly run picks them up.
    """
    result = import_logpush()
    logger.info(
        "import_logpush_task: files=%d events=%d error=%r", result.files_imported, result.events, result.error
    )
```

In `config/celery.py` `app.conf.beat_schedule`, add:

```python
    "import-logpush": {
        "task": "apps.usage_tracking.tasks.import_logpush_task",
        # Minute 10: Logpush delivers within minutes; offset from the other usage jobs.
        "schedule": crontab(minute=10),
    },
```

- [ ] **Step 9: Run the importer tests and the existing task tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_logpush_import.py apps/usage_tracking/tests/test_tasks.py`
Expected: all passed.

- [ ] **Step 10: Checkpoint** — no commit.

---

### Task 7: R2 reconciliation import

**Files:**
- Create: `apps/usage_tracking/services/r2_reads_client.py`, `apps/usage_tracking/services/r2_reconciliation.py`
- Modify: `apps/usage_tracking/tasks.py`, `config/celery.py`
- Test: `apps/usage_tracking/tests/test_r2_reconciliation.py`

**Interfaces:**
- Consumes: `CF_GRAPHQL_URL`, `CloudflareGraphQLError` (cf_analytics_client);
  `parse_download_path`; Task 5 repository (`edge_requests_by_object`, `replace_r2_reads`,
  `R2_RECONCILIATION_JOB`, locks/state); settings `CF_ACCOUNT_ID`, `USAGE_ANALYTICS_API_TOKEN`,
  `CLOUDFLARE_R2_BUCKET`, `ENABLE_USAGE_R2_RECONCILIATION`.
- Produces: `R2ReadsClient(account_tag, api_token).fetch_reads(bucket, start, end, limit=10000) ->
  tuple[dict[str, int], bool]` (object → successful GetObject count, truncated flag);
  `reconcile_r2_reads(now=None) -> ReconcileResult(hours: int, error: str)`; task
  `reconcile_r2_reads_task` (beat: minute 40).

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_r2_reconciliation.py
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import override_settings

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    R2ObjectReadsHourly,
    TrafficChannel,
    TrafficEvent,
    TrafficKind,
    TrafficPlatform,
    TrafficStatusClass,
)
from apps.usage_tracking.services import r2_reads_client, r2_reconciliation
from apps.usage_tracking.services.r2_reads_client import R2ReadsClient
from apps.usage_tracking.services.r2_reconciliation import reconcile_r2_reads

NOW = datetime(2026, 10, 18, 12, 40, tzinfo=UTC)
# Last complete hour reconciled: floor(12:40 - 3 h) = 09:00 is the exclusive end, so 08:00.
H8 = datetime(2026, 10, 18, 8, tzinfo=UTC)
KEY = "media/uploads/assets/13/recitations/091.mp3"


class TestR2ReadsClient:
    def test_fetch_reads_where_groups_returned_should_sum_successful_reads_per_object(self):
        # Arrange
        groups = [
            {"sum": {"requests": 5}, "dimensions": {"objectName": KEY, "actionStatus": "success"}},
            {"sum": {"requests": 2}, "dimensions": {"objectName": KEY, "actionStatus": "userError"}},
        ]
        response = MagicMock()
        response.json.return_value = {"data": {"viewer": {"accounts": [{"r2OperationsAdaptiveGroups": groups}]}}}

        # Act
        with patch.object(r2_reads_client.requests, r2_reads_client.requests.post.__name__, return_value=response):
            reads, truncated = R2ReadsClient("acc", "token").fetch_reads("bucket", H8, H8 + timedelta(hours=1))

        # Assert
        assert (reads, truncated) == ({KEY: 5}, False)


@override_settings(
    ENABLE_USAGE_R2_RECONCILIATION=True,
    CF_ACCOUNT_ID="acc",
    USAGE_ANALYTICS_API_TOKEN="token",
    CLOUDFLARE_R2_BUCKET="assets",
)
class TestReconcile(BaseTestCase):
    def test_reconcile_r2_reads_where_reads_exceed_edge_should_store_both_counts(self):
        # Arrange
        TrafficEvent.objects.create(
            ray_id="r1",
            occurred_at=H8 + timedelta(minutes=5),
            kind=TrafficKind.AUDIO_SURAH,
            asset_id=13,
            surah=91,
            country="SA",
            channel=TrafficChannel.WEB,
            platform=TrafficPlatform.WEB,
            status_class=TrafficStatusClass.FULL,
            listener_id="a" * 64,
            ua_family="browser",
            path="/" + KEY,
        )
        client = MagicMock(spec=R2ReadsClient)
        client.fetch_reads.side_effect = lambda bucket, start, end: (({KEY: 3}, False) if start == H8 else ({}, False))

        # Act
        with patch.object(r2_reconciliation, r2_reconciliation._build_client.__name__, return_value=client):
            result = reconcile_r2_reads(NOW)

        # Assert
        row = R2ObjectReadsHourly.objects.get(hour=H8)
        assert (row.asset_id, row.reads, row.edge_requests) == (13, 3, 1)
        assert result.error == ""
        assert result.hours == 24  # refresh window: the 24 complete hours ending 3 h before now

    def test_reconcile_r2_reads_where_disabled_should_do_nothing(self):
        # Act
        with self.settings(ENABLE_USAGE_R2_RECONCILIATION=False):
            result = reconcile_r2_reads(NOW)

        # Assert
        assert result.hours == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_r2_reconciliation.py`
Expected: FAIL — `ModuleNotFoundError: ... r2_reads_client`.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/services/r2_reads_client.py
"""Cloudflare GraphQL client for R2 per-object reads (any access route, aggregated)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from apps.usage_tracking.services.cf_analytics_client import CF_GRAPHQL_URL, CloudflareGraphQLError

_REQUEST_TIMEOUT_SECONDS = 30
_QUERY = """
query R2ObjectReads($accountTag: String!, $bucket: String!, $start: Time!, $end: Time!, $limit: Int!) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      r2OperationsAdaptiveGroups(
        limit: $limit
        filter: { datetime_geq: $start, datetime_lt: $end, bucketName: $bucket, actionType: "GetObject" }
      ) {
        sum { requests }
        dimensions { objectName actionStatus }
      }
    }
  }
}
"""


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class R2ReadsClient:
    def __init__(self, account_tag: str, api_token: str) -> None:
        self._account_tag = account_tag
        self._api_token = api_token

    def fetch_reads(self, bucket: str, start: datetime, end: datetime, limit: int = 10000) -> tuple[dict[str, int], bool]:
        response = requests.post(
            CF_GRAPHQL_URL,
            json={
                "query": _QUERY,
                "variables": {
                    "accountTag": self._account_tag,
                    "bucket": bucket,
                    "start": _format_time(start),
                    "end": _format_time(end),
                    "limit": limit,
                },
            },
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("errors"):
            raise CloudflareGraphQLError(str(payload["errors"]))
        accounts = ((payload.get("data") or {}).get("viewer") or {}).get("accounts") or []
        if not accounts:
            raise CloudflareGraphQLError("no account matched CF_ACCOUNT_ID (check token scope)")
        groups = accounts[0]["r2OperationsAdaptiveGroups"]
        reads: dict[str, int] = {}
        for group in groups:
            if group["dimensions"]["actionStatus"] != "success":
                continue
            name = group["dimensions"]["objectName"]
            reads[name] = reads.get(name, 0) + int(group["sum"]["requests"])
        return reads, len(groups) >= limit
```

```python
# apps/usage_tracking/services/r2_reconciliation.py
"""Hourly R2 read counts per asset object, beside the edge requests seen for the same object.

R2 counts reads from every route (custom domain, presigned URLs, r2.dev); the difference to the
edge count is traffic the Logpush import cannot see. The last 24 hours are re-done every run,
because Logpush files and R2 analytics both arrive with some delay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

from django.conf import settings

from apps.usage_tracking.models import R2ObjectReadsHourly
from apps.usage_tracking.repositories.traffic import R2_RECONCILIATION_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.download_paths import parse_download_path
from apps.usage_tracking.services.r2_reads_client import R2ReadsClient

logger = logging.getLogger(__name__)

_HOUR = timedelta(hours=1)
_LAG = timedelta(hours=3)  # leave time for the hourly Logpush import to cover the hour
_REFRESH = timedelta(hours=24)
_MAX_HOURS_PER_RUN = 48


@dataclass(frozen=True, slots=True)
class ReconcileResult:
    hours: int
    error: str


def _build_client() -> R2ReadsClient:
    return R2ReadsClient(account_tag=settings.CF_ACCOUNT_ID, api_token=settings.USAGE_ANALYTICS_API_TOKEN)


def reconcile_r2_reads(now: datetime | None = None) -> ReconcileResult:
    if not settings.ENABLE_USAGE_R2_RECONCILIATION:
        logger.info("reconcile_r2_reads: disabled via ENABLE_USAGE_R2_RECONCILIATION; skipping")
        return ReconcileResult(0, "")
    if not (settings.CF_ACCOUNT_ID and settings.USAGE_ANALYTICS_API_TOKEN and settings.CLOUDFLARE_R2_BUCKET):
        logger.warning("reconcile_r2_reads: missing CF_ACCOUNT_ID/USAGE_ANALYTICS_API_TOKEN/CLOUDFLARE_R2_BUCKET; skipping")
        return ReconcileResult(0, "")

    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(R2_RECONCILIATION_JOB):
        return ReconcileResult(0, "")

    hours = 0
    error = ""
    try:
        client = _build_client()
        end = floor_hour(now - _LAG)
        watermark = repo.get_watermark(R2_RECONCILIATION_JOB)
        hour = min(watermark, end - _REFRESH) if watermark else end - _REFRESH
        while hour < end and hours < _MAX_HOURS_PER_RUN:
            reads, truncated = client.fetch_reads(settings.CLOUDFLARE_R2_BUCKET, hour, hour + _HOUR)
            if truncated:
                logger.error("reconcile_r2_reads: hour %s hit the page limit; counts are partial", hour)
            edge = repo.edge_requests_by_object(hour)
            rows = []
            for key, count in reads.items():
                file = parse_download_path("/" + key)
                if file is None:
                    continue
                rows.append(
                    R2ObjectReadsHourly(
                        hour=hour,
                        object_key=key[:512],
                        asset_id=file.asset_id,
                        reads=count,
                        edge_requests=edge.get("/" + key, 0),
                    )
                )
            repo.replace_r2_reads(hour, rows)
            hour += _HOUR
            hours += 1
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("reconcile_r2_reads: run failed after %d hour(s)", hours)
    finally:
        try:
            repo.record_run(R2_RECONCILIATION_JOB, now, error)
        finally:
            repo.unlock(R2_RECONCILIATION_JOB)
    return ReconcileResult(hours, error)
```

In `tasks.py` add `from apps.usage_tracking.services.r2_reconciliation import reconcile_r2_reads` and:

```python
@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def reconcile_r2_reads_task() -> None:
    """Record R2 reads per asset object (see `r2_reconciliation`)."""
    result = reconcile_r2_reads()
    logger.info("reconcile_r2_reads_task: hours=%d error=%r", result.hours, result.error)
```

In `config/celery.py` add:

```python
    "reconcile-r2-reads": {
        "task": "apps.usage_tracking.tasks.reconcile_r2_reads_task",
        "schedule": crontab(minute=40),
    },
```

- [ ] **Step 4: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_r2_reconciliation.py`
Expected: all passed.

- [ ] **Step 5: Checkpoint** — no commit.

---

### Task 8: Nightly maintenance (monthly uniques, retention purge)

**Files:**
- Create: `apps/usage_tracking/services/traffic_maintenance.py`
- Modify: `apps/usage_tracking/tasks.py`, `config/celery.py`
- Test: `apps/usage_tracking/tests/test_traffic_maintenance.py`

**Interfaces:**
- Consumes: Task 5 `rebuild_month_uniques`, `purge_events_before`, `MAINTENANCE_JOB`, locks;
  setting `USAGE_EVENT_RETENTION_MONTHS`.
- Produces: `add_months(month: date, months: int) -> date`,
  `run_usage_maintenance(now: datetime | None = None) -> int` (events purged; 0 when skipped);
  task `usage_maintenance_task` (beat: 03:30 UTC).

- [ ] **Step 1: Write the failing tests**

```python
# apps/usage_tracking/tests/test_traffic_maintenance.py
from datetime import UTC, date, datetime
from unittest.mock import patch

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.repositories.traffic import TrafficRepository
from apps.usage_tracking.services.traffic_maintenance import add_months, run_usage_maintenance

NOW = datetime(2026, 1, 15, 3, 30, tzinfo=UTC)


class TestAddMonths:
    def test_add_months_where_crossing_year_should_wrap(self):
        # Act / Assert
        assert add_months(date(2026, 1, 1), -1) == date(2025, 12, 1)
        assert add_months(date(2026, 1, 1), -25) == date(2023, 12, 1)
        assert add_months(date(2025, 12, 1), 1) == date(2026, 1, 1)


class TestRunUsageMaintenance(BaseTestCase):
    def test_run_usage_maintenance_where_run_should_rebuild_two_months_and_purge_by_retention(self):
        # Arrange
        with (
            patch.object(TrafficRepository, TrafficRepository.rebuild_month_uniques.__name__) as rebuild,
            patch.object(TrafficRepository, TrafficRepository.purge_events_before.__name__, return_value=3) as purge,
            self.settings(USAGE_EVENT_RETENTION_MONTHS=25),
        ):
            # Act
            deleted = run_usage_maintenance(NOW)

        # Assert
        assert [call.args[0] for call in rebuild.call_args_list] == [date(2025, 12, 1), date(2026, 1, 1)]
        purge.assert_called_once_with(datetime(2023, 12, 1, tzinfo=UTC))
        assert deleted == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_maintenance.py`
Expected: FAIL — `ModuleNotFoundError: ... traffic_maintenance`.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/services/traffic_maintenance.py
"""Nightly upkeep: monthly unique counts (kept forever) and raw-event retention."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
import logging

from django.conf import settings

from apps.usage_tracking.repositories.traffic import MAINTENANCE_JOB, TrafficRepository

logger = logging.getLogger(__name__)


def add_months(month: date, months: int) -> date:
    """First day of the month `months` away from `month`'s month."""
    years, index = divmod(month.month - 1 + months, 12)
    return date(month.year + years, index + 1, 1)


def run_usage_maintenance(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(MAINTENANCE_JOB):
        return 0
    try:
        this_month = now.date().replace(day=1)
        # The previous month too: late Logpush files can still land in it during the first days.
        for month in (add_months(this_month, -1), this_month):
            repo.rebuild_month_uniques(month)
        cutoff = datetime.combine(add_months(this_month, -settings.USAGE_EVENT_RETENTION_MONTHS), time.min, tzinfo=UTC)
        deleted = repo.purge_events_before(cutoff)
        logger.info("usage_maintenance: rebuilt monthly uniques; purged %d event(s) before %s", deleted, cutoff)
        return deleted
    finally:
        repo.unlock(MAINTENANCE_JOB)
```

In `tasks.py` add `from apps.usage_tracking.services.traffic_maintenance import run_usage_maintenance` and:

```python
@shared_task(acks_late=True, soft_time_limit=1500, time_limit=1560, ignore_result=True)
def usage_maintenance_task() -> None:
    """Rebuild monthly unique counts and purge expired traffic events."""
    run_usage_maintenance()
```

In `config/celery.py` add:

```python
    "usage-maintenance": {
        "task": "apps.usage_tracking.tasks.usage_maintenance_task",
        "schedule": crontab(minute=30, hour=3),
    },
```

- [ ] **Step 4: Run the tests**

Run: `uv run --frozen pytest -q apps/usage_tracking/tests/test_traffic_maintenance.py`
Expected: all passed.

- [ ] **Step 5: Checkpoint** — no commit.

---

### Task 9: Env files, CI/CD wiring, docs, spec amendments, full verification

**Files:**
- Modify: `env.example`, `deployment/docker/env.template`, `.github/workflows/ci-cd.yml`,
  `docs/ARCHITECTURE.md`, `README.md`, `docs/superpowers/specs/2026-10-18-usage-reports-design.md`

- [ ] **Step 1: Env files** — append after the `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS=` line in both
  `env.example` and `deployment/docker/env.template`:

```
# Usage reports (Cloudflare Logpush import + R2 reconciliation); all optional
ENABLE_USAGE_LOGPUSH_IMPORT=False
USAGE_LOGS_BUCKET=itqan-usage-logs
USAGE_LOGS_PREFIX=http/production/
USAGE_LOGS_ACCESS_KEY_ID=
USAGE_LOGS_SECRET_ACCESS_KEY=
USAGE_LOGPUSH_MAX_FILES_PER_RUN=500
ENABLE_USAGE_R2_RECONCILIATION=False
CF_ACCOUNT_ID=
USAGE_ANALYTICS_API_TOKEN=
USAGE_IDENTITY_KEY=
USAGE_EVENT_RETENTION_MONTHS=25
```

- [ ] **Step 2: CI/CD** — in `.github/workflows/ci-cd.yml`, after the
  `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` echo line of the **staging** block add:

```
                echo "ENABLE_USAGE_LOGPUSH_IMPORT=${{ vars.STAGING_ENABLE_USAGE_LOGPUSH_IMPORT || 'False' }}";
                echo "USAGE_LOGS_BUCKET=${{ vars.STAGING_USAGE_LOGS_BUCKET || 'itqan-usage-logs' }}";
                echo "USAGE_LOGS_PREFIX=${{ vars.STAGING_USAGE_LOGS_PREFIX || 'http/staging/' }}";
                echo "USAGE_LOGS_ACCESS_KEY_ID=${{ secrets.STAGING_USAGE_LOGS_ACCESS_KEY_ID }}";
                echo "USAGE_LOGS_SECRET_ACCESS_KEY=${{ secrets.STAGING_USAGE_LOGS_SECRET_ACCESS_KEY }}";
                echo "USAGE_LOGPUSH_MAX_FILES_PER_RUN=${{ vars.STAGING_USAGE_LOGPUSH_MAX_FILES_PER_RUN || '500' }}";
                echo "ENABLE_USAGE_R2_RECONCILIATION=${{ vars.STAGING_ENABLE_USAGE_R2_RECONCILIATION || 'False' }}";
                echo "CF_ACCOUNT_ID=${{ vars.CF_ACCOUNT_ID }}";
                echo "USAGE_ANALYTICS_API_TOKEN=${{ secrets.USAGE_ANALYTICS_API_TOKEN }}";
                echo "USAGE_IDENTITY_KEY=${{ secrets.STAGING_USAGE_IDENTITY_KEY }}";
                echo "USAGE_EVENT_RETENTION_MONTHS=${{ vars.STAGING_USAGE_EVENT_RETENTION_MONTHS || '25' }}";
```

  and the same in the **production** block with `PROD_` prefixes and
  `USAGE_LOGS_PREFIX=${{ vars.PROD_USAGE_LOGS_PREFIX || 'http/production/' }}`
  (`CF_ACCOUNT_ID` and `USAGE_ANALYTICS_API_TOKEN` are shared, unprefixed). Validate:
  `uv run --frozen python -c "import yaml;yaml.safe_load(open('.github/workflows/ci-cd.yml'))"`.

- [ ] **Step 3: README** — after the asset-download-statistics table add a
  "Usage reports (Logpush)" table listing the 11 settings above with defaults and one-line
  meanings (as in spec §13), plus: "S3 credentials for the logs bucket come from the Cloudflare
  token: access key id = token id, secret = SHA-256 of the token value."

- [ ] **Step 4: ARCHITECTURE.md** — add a "Usage reports: traffic collection" section after
  "Asset download statistics": the flow diagram from spec §4, the model table from spec §7 (with
  the amendments above), the three jobs and their schedules (import minute 10, reconciliation
  minute 40, maintenance 03:30 UTC), the channel rules (spec §5.1), identity (spec §6), and
  "the 2026-10-13 GraphQL sync remains until cutover".

- [ ] **Step 5: Spec amendments** — apply the eight "Spec amendments made by this plan" to
  `docs/superpowers/specs/2026-10-18-usage-reports-design.md` (§7 table, §5.1 note, §13 row for
  `USAGE_LOGPUSH_MAX_FILES_PER_RUN`, §4.1 drop `host_env` wording, §6 `end_user_id`).

- [ ] **Step 6: Localization check** — this plan adds no `_()` strings; confirm:

Run: `uv run --frozen manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header && msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null`
Expected: `0 untranslated` (no new entries); revert any `.po` churn that is only header dates.

- [ ] **Step 7: Full verification**

Run: `uv run --frozen pre-commit run --files $(git status --porcelain | awk '{print $2}' | grep -E '\.(py|yml|md)$')`
Expected: all hooks pass (fix and re-run on formatting rewrites).

Run: `uv run --frozen manage.py makemigrations --check --dry-run`
Expected: only the pre-existing `djangosaml2idp` drift.

Run: `uv run --frozen pytest -q -p no:cacheprovider --create-db`
Expected: full suite green (baseline before this plan: 2519 passed, 18 skipped, plus this plan's
new tests).

- [ ] **Step 8: Performance check** (per the check-performance memory) — with 50k synthetic
  events in one hour, `rebuild_hour` must finish in under 2 s locally:

```bash
uv run --frozen python manage.py shell -c "
from datetime import UTC, datetime, timedelta; import time, random
from apps.usage_tracking.models import *
from apps.usage_tracking.repositories.traffic import TrafficRepository
h = datetime(2030, 1, 1, 10, tzinfo=UTC)
TrafficEvent.objects.bulk_create([TrafficEvent(ray_id=f'perf{i}', occurred_at=h + timedelta(seconds=i % 3600), kind='audio_surah', asset_id=random.randint(1, 50), surah=random.randint(1, 114), country='SA', channel='app_unidentified', platform='android', status_class='full', listener_id=f'{random.randint(1, 5000):064d}', ua_family='dalvik', path='/p') for i in range(50000)], batch_size=5000)
t = time.time(); TrafficRepository().rebuild_hour(h, timedelta(minutes=5)); print('rebuild_hour', round(time.time() - t, 2), 's')
TrafficEvent.objects.filter(ray_id__startswith='perf').delete(); TrafficHourly.objects.filter(hour=h).delete(); TrafficDaily.objects.filter(day=h.date()).delete()
"
```

Expected: `rebuild_hour` under 2 s. If slower, `EXPLAIN ANALYZE` the session query and adjust
`traffic_event_session_idx` before continuing.

- [ ] **Step 9: Checkpoint** — report to the user; commits only with their permission (one
  commit per task is a natural split: models, classify, identity, parser, repository, importer,
  reconciliation, maintenance, wiring + docs).

---

## After this plan (not part of it)

Cloudflare step 0 with the user (spec §12 steps 1–3, staging first): lifecycle rule, token
check from staging, Logpush job for staging hosts with custom fields; then set
`STAGING_USAGE_LOGS_*`, `CF_ACCOUNT_ID`, `USAGE_ANALYTICS_API_TOKEN`,
`STAGING_USAGE_IDENTITY_KEY`, enable the import on staging and run the staging end-to-end check.
Plans 2–6 are written next: (2) attribution and Django events, (3) reports API, (4) frontend,
(5) CLI, (6) cutover.
