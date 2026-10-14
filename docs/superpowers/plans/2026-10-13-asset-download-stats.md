# Asset Download Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import per-request download data for asset files from Cloudflare edge analytics every hour, store it as raw events plus hourly/daily rollups, and expose publisher-scoped statistics through the portal API.

**Architecture:** A Celery beat task pulls one UTC hour at a time from Cloudflare GraphQL (`httpRequestsAdaptive` for individual requests, `httpRequestsAdaptiveGroups` for request/byte totals), parses file paths into assets, and replaces that hour's events, hourly rows and daily rows in one transaction, advancing a watermark. Portal GET endpoints aggregate the rollups, scoped with `request.publisher_q()`.

**Tech Stack:** Django 5.2, django-ninja 1.5, Celery beat, PostgreSQL (window functions, advisory locks), `requests`, pytest + model_bakery.

**Spec:** `docs/superpowers/specs/2026-10-13-asset-download-stats-design.md`

## Global Constraints

- Work only in the worktree `../itqan-cms-backend-download-stats` (branch `feat/asset-download-stats`). Another agent is working in `../itqan-cms-backend`; never touch it.
- **Never run `git commit`.** The user commits manually (repo rule). Tasks end with a test run, not a commit.
- Python 3.13, Django 5.2; every non-endpoint function is type-hinted.
- Tests: subclass `apps.core.tests.base.BaseTestCase` for anything touching the DB (raw `django.test.TestCase` breaks the suite); plain pytest classes for pure functions.
- Test names: `test_<function_name>_where_<criteria>_should_<expected>`; explicit `# Arrange` / `# Act` / `# Assert` comments; `self.authenticate_user(...)` inside the test body, never in `setUp`.
- 4xx API tests assert `error_name` as well as the status code.
- Patch with `patch.object(<module or class>, <symbol>.__name__, ...)` on the call-site module; no dotted-path strings.
- Never import or patch `sentry_sdk` (prod-only extra). Errors reach Sentry through `logger.error` / `logger.exception`.
- Every user-facing message uses `gettext_lazy as _`; after the API task, run makemessages, add Arabic `msgstr`s, and `msgfmt --check --statistics` must report 0 untranslated.
- All new settings are optional with defaults: `ENABLE_ASSET_DOWNLOAD_SYNC=False`, `ASSET_DOWNLOAD_SYNC_LAG_MINUTES=15`, `ASSET_DOWNLOAD_SYNC_REFRESH_HOURS=2`, `ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN=24`, `ASSET_DOWNLOAD_SYNC_STALE_HOURS=6`, `ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES=5`, `ASSET_DOWNLOAD_EVENT_RETENTION_DAYS` unset.
- All bucketing is UTC. A play = same `client_hash` + same file with gaps ≤ 5 minutes, credited to the starting request's row.
- The existing Mixpanel sync (`sync_audio_usage_task`, `cf_analytics_client.py`, `audio_usage_sync.py`) is not modified.
- Run commands from the worktree root with `uv run` (or `.venv/bin/...` if present).

## Review Focus

1. **Cloudflare returns a country that is empty or longer than 2 chars** (e.g. `""`, `"T1"` is fine, `None`) — expected: stored as `XX` or the first two upper-cased chars, never a DB error. Test in Task 3 (`build_event_rows`).
2. **Same request appears in two overlapping fetches** (a split boundary or a re-run) — expected: one event row, no `IntegrityError`. Test in Task 4 (`replace_hour` re-run) and Task 3 (`fetch_complete` boundaries are half-open).
3. **A play that started in the previous hour continues into this hour** — expected: not counted again in this hour. Test in Task 4.
4. **Publisher member without `X-Tenant` who belongs to no publisher** — expected: empty stats, not other publishers' data. Test in Task 6.
5. **`end_date` before `start_date`, or a month range spanning a year boundary** — expected: 400 `invalid_range`; month buckets ordered across the year correctly. Test in Task 6.

---

## File Map

| File | Responsibility |
|---|---|
| `config/settings/base.py` (modify) | Install `apps.usage_tracking` unconditionally; new settings |
| `env.example`, `deployment/docker/env.template` (modify) | Document new settings |
| `apps/usage_tracking/models.py` (create) | `AssetDownloadEvent`, `AssetDownloadHourly`, `AssetDownloadDaily`, `UsageSyncState`, choices |
| `apps/usage_tracking/migrations/0001_initial.py` (generated) | Tables |
| `apps/usage_tracking/services/download_paths.py` (create) | Path → file parsing, status class, client hash |
| `apps/usage_tracking/services/cf_downloads_client.py` (create) | Cloudflare GraphQL queries (events, totals, dataset limits) |
| `apps/usage_tracking/repositories/asset_downloads.py` (create) | All writes: replace an hour, plays SQL, daily rebuild, state, lock, purge |
| `apps/usage_tracking/services/asset_download_sync.py` (create) | Hour planning, splitting, orchestration |
| `apps/usage_tracking/tasks.py` (modify) | `sync_asset_downloads_task` |
| `config/celery.py` (modify) | Beat entry at minute 20 |
| `apps/core/permissions.py` (modify) | `PORTAL_READ_USAGE` |
| `apps/publishers/services/publisher_member_service.py` (modify) | Grant it to `Publisher Member` |
| `apps/usage_tracking/api/portal/downloads.py` (create) | Summary / timeseries / breakdown endpoints (portal reads query models directly, per repo rule) |
| `locale/ar/LC_MESSAGES/django.po` (modify) | Arabic strings |
| `docs/ARCHITECTURE.md`, `README.md` (modify) | Docs |
| Tests under `apps/usage_tracking/tests/` | One file per unit |

---

### Task 0: Worktree environment

**Files:** `.env` (gitignored, local only)

- [ ] **Step 1: Copy the env file and isolate the database name**

The other agent runs tests against `test_<DB_NAME>` from the main checkout; using the same name with `--reuse-db` would clobber its test database.

```bash
cp ../itqan-cms-backend/.env .env
sed -i '' 's/^DB_NAME=\(.*\)$/DB_NAME=\1_dlstats/' .env
grep '^DB_NAME=' .env
```
Expected: `DB_NAME=<original>_dlstats`

- [ ] **Step 2: Install dependencies**

Run: `uv sync --group dev`
Expected: exits 0.

- [ ] **Step 3: Baseline the existing app tests**

Run: `uv run pytest apps/usage_tracking -q --create-db`
Expected: all pass (board-url tests skipped when `MIXPANEL_ENABLED=False`). Record the pass count.

---

### Task 1: Always install the app, add settings and models

The app is currently installed only when `MIXPANEL_ENABLED`; the new tables must exist regardless.

**Files:**
- Modify: `config/settings/base.py:633-648`
- Modify: `env.example:72-76`, `deployment/docker/env.template` (append)
- Create: `apps/usage_tracking/models.py`
- Create: `apps/usage_tracking/migrations/__init__.py`, generated `0001_initial.py`
- Test: `apps/usage_tracking/tests/test_models.py`

**Interfaces:**
- Produces: `AssetDownloadFileKind` (`SURAH="surah"`, `AYAH="ayah"`, `VERSION="version"`), `AssetDownloadStatusClass` (`FULL="full"`, `PARTIAL="partial"`, `OTHER="other"`), models `AssetDownloadEvent`, `AssetDownloadHourly`, `AssetDownloadDaily`, `UsageSyncState`; constant `ROLLUP_DIMENSIONS: tuple[str, ...] = ("asset_id", "file_kind", "surah", "asset_version_id", "country", "status_class")`; settings listed in Global Constraints.

- [ ] **Step 1: Write the failing test**

`apps/usage_tracking/tests/test_models.py`:

```python
from datetime import UTC, date, datetime

from django.db import IntegrityError, transaction

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
)


def _hourly(**overrides) -> AssetDownloadHourly:
    values = {
        "hour": datetime(2026, 10, 13, 10, tzinfo=UTC),
        "asset_id": 1,
        "file_kind": AssetDownloadFileKind.SURAH,
        "surah": 1,
        "asset_version_id": None,
        "country": "SA",
        "status_class": AssetDownloadStatusClass.FULL,
        "requests": 1,
        "bytes": 10,
        "plays": 1,
    }
    values.update(overrides)
    return AssetDownloadHourly(**values)


class TestAssetDownloadHourly(BaseTestCase):
    def test_unique_constraint_where_null_version_rows_duplicate_should_raise(self):
        # Arrange
        _hourly().save()

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            _hourly().save()


class TestAssetDownloadDaily(BaseTestCase):
    def test_unique_constraint_where_null_surah_rows_duplicate_should_raise(self):
        # Arrange
        kwargs = {
            "day": date(2026, 10, 13),
            "asset_id": 1,
            "file_kind": AssetDownloadFileKind.VERSION,
            "surah": None,
            "asset_version_id": None,
            "country": "SA",
            "status_class": AssetDownloadStatusClass.FULL,
        }
        AssetDownloadDaily.objects.create(**kwargs)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetDownloadDaily.objects.create(**kwargs)


class TestAssetDownloadEvent(BaseTestCase):
    def test_ray_id_where_duplicated_should_raise(self):
        # Arrange
        kwargs = {
            "ray_id": "a49d7f1abc4ee1e0",
            "occurred_at": datetime(2026, 10, 13, 10, 0, 18, tzinfo=UTC),
            "asset_id": 13,
            "file_kind": AssetDownloadFileKind.SURAH,
            "surah": 91,
            "country": "SA",
            "status_class": AssetDownloadStatusClass.FULL,
            "client_hash": "x" * 64,
        }
        AssetDownloadEvent.objects.create(**kwargs)

        # Act / Assert
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssetDownloadEvent.objects.create(**kwargs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/usage_tracking/tests/test_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'AssetDownloadDaily'`.

- [ ] **Step 3: Install the app unconditionally and add settings**

In `config/settings/base.py`, replace

```python
if MIXPANEL_ENABLED:
    LOCAL_APPS.append("apps.usage_tracking")
```

with

```python
# Always installed: holds the asset download statistics tables, which do not depend on
# Mixpanel. Mixpanel behaviour stays gated by MIXPANEL_ENABLED inside the app.
LOCAL_APPS.append("apps.usage_tracking")
```

After the `AUDIO_USAGE_SYNC_WINDOW_HOURS` line add:

```python

# Asset download statistics from Cloudflare edge analytics (reuses CF_ZONE_ID,
# CF_API_TOKEN and CF_R2_CUSTOM_DOMAIN). All optional.
ENABLE_ASSET_DOWNLOAD_SYNC = config("ENABLE_ASSET_DOWNLOAD_SYNC", default=False, cast=bool)
ASSET_DOWNLOAD_SYNC_LAG_MINUTES = config("ASSET_DOWNLOAD_SYNC_LAG_MINUTES", default=15, cast=int)
ASSET_DOWNLOAD_SYNC_REFRESH_HOURS = config("ASSET_DOWNLOAD_SYNC_REFRESH_HOURS", default=2, cast=int)
ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN = config("ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN", default=24, cast=int)
ASSET_DOWNLOAD_SYNC_STALE_HOURS = config("ASSET_DOWNLOAD_SYNC_STALE_HOURS", default=6, cast=int)
ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES = config("ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES", default=5, cast=int)
# Unset/empty keeps raw download events forever; rollups are never trimmed.
ASSET_DOWNLOAD_EVENT_RETENTION_DAYS = config(
    "ASSET_DOWNLOAD_EVENT_RETENTION_DAYS", default="", cast=lambda value: int(value) if value else None
)
```

Append to `env.example` after `AUDIO_USAGE_SYNC_WINDOW_HOURS=6` and to the end of `deployment/docker/env.template`:

```
# Asset download statistics (optional; defaults shown)
ENABLE_ASSET_DOWNLOAD_SYNC=False
ASSET_DOWNLOAD_SYNC_LAG_MINUTES=15
ASSET_DOWNLOAD_SYNC_REFRESH_HOURS=2
ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN=24
ASSET_DOWNLOAD_SYNC_STALE_HOURS=6
ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES=5
ASSET_DOWNLOAD_EVENT_RETENTION_DAYS=
```

- [ ] **Step 4: Create the models**

`apps/usage_tracking/migrations/__init__.py`: empty file.

`apps/usage_tracking/models.py`:

```python
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
    file_kind = models.CharField(max_length=8, choices=AssetDownloadFileKind.choices)
    surah = models.PositiveSmallIntegerField(null=True, blank=True)
    asset_version_id = models.PositiveIntegerField(null=True, blank=True)
    country = models.CharField(max_length=2)
    status_class = models.CharField(max_length=8, choices=AssetDownloadStatusClass.choices)

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
            models.UniqueConstraint(
                fields=["hour", *ROLLUP_DIMENSIONS], name="uniq_dl_hourly", nulls_distinct=False
            ),
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
```

- [ ] **Step 5: Generate the migration**

Branch switching leaves the local DB's migration history inconsistent; point `makemigrations` at a database that does not exist so it skips the consistency check.

Run: `DB_NAME=nonexistent_dlstats uv run python manage.py makemigrations usage_tracking`
Expected: `apps/usage_tracking/migrations/0001_initial.py` created with the four models. Open it and confirm `nulls_distinct=False` on both constraints.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_models.py -q --create-db`
Expected: 3 passed.

- [ ] **Step 7: Confirm installing the app broke nothing**

Run: `uv run pytest apps/usage_tracking apps/content/tests/public -q`
Expected: same pass count as the Task 0 baseline plus 3; no new failures.

---

### Task 2: Path parsing, status class, client hash

**Files:**
- Create: `apps/usage_tracking/services/download_paths.py`
- Test: `apps/usage_tracking/tests/test_download_paths.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True, slots=True) class DownloadFile: asset_id: int; file_kind: str; surah: int | None; asset_version_id: int | None`
  - `parse_download_path(path: str) -> DownloadFile | None`
  - `status_class_for(status: int) -> str`
  - `client_hash_for(ip: str, day: date) -> str` (64 hex chars)
  - `normalize_country(value: str | None) -> str`
  - `ASSET_PATH_LIKE: str = "/media/uploads/assets/%"`

- [ ] **Step 1: Write the failing tests**

`apps/usage_tracking/tests/test_download_paths.py`:

```python
from datetime import date

from django.test import override_settings

from apps.usage_tracking.models import AssetDownloadFileKind, AssetDownloadStatusClass
from apps.usage_tracking.services.download_paths import (
    DownloadFile,
    client_hash_for,
    normalize_country,
    parse_download_path,
    status_class_for,
)


class TestParseDownloadPath:
    def test_parse_download_path_where_surah_mp3_should_return_surah_file(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/13/recitations/091.mp3")

        # Assert
        assert parsed == DownloadFile(13, AssetDownloadFileKind.SURAH, 91, None)

    def test_parse_download_path_where_surah_has_other_extension_should_return_surah_file(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/7/recitations/002.m4a")

        # Assert
        assert parsed == DownloadFile(7, AssetDownloadFileKind.SURAH, 2, None)

    def test_parse_download_path_where_ayah_audio_should_collapse_to_surah(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/5/recitations/12/002/ayah_255.mp3")

        # Assert
        assert parsed == DownloadFile(5, AssetDownloadFileKind.AYAH, 2, None)

    def test_parse_download_path_where_version_file_should_return_version_id(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/9/versions/44/mushaf-hafs.zip")

        # Assert
        assert parsed == DownloadFile(9, AssetDownloadFileKind.VERSION, None, 44)

    def test_parse_download_path_where_tmp_version_folder_should_return_null_version(self):
        # Act
        parsed = parse_download_path("/media/uploads/assets/9/versions/tmp-1a2b3c4d/file.json")

        # Assert
        assert parsed == DownloadFile(9, AssetDownloadFileKind.VERSION, None, None)

    def test_parse_download_path_where_thumbnail_or_preview_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/media/uploads/assets/9/cover.png") is None
        assert parse_download_path("/media/uploads/assets/9/preview/shot.png") is None
        assert parse_download_path("/media/uploads/reciters/3/icon.png") is None

    def test_parse_download_path_where_no_media_prefix_should_return_none(self):
        # Act / Assert
        assert parse_download_path("/uploads/assets/13/recitations/091.mp3") is None


class TestStatusClassFor:
    def test_status_class_for_where_known_statuses_should_map_to_classes(self):
        # Act / Assert
        assert status_class_for(200) == AssetDownloadStatusClass.FULL
        assert status_class_for(206) == AssetDownloadStatusClass.PARTIAL
        assert status_class_for(304) == AssetDownloadStatusClass.OTHER
        assert status_class_for(404) == AssetDownloadStatusClass.OTHER


class TestNormalizeCountry:
    def test_normalize_country_where_value_missing_or_odd_should_return_two_upper_chars(self):
        # Act / Assert
        assert normalize_country("SA") == "SA"
        assert normalize_country("sa") == "SA"
        assert normalize_country("") == "XX"
        assert normalize_country(None) == "XX"
        assert normalize_country("T1") == "T1"
        assert normalize_country("XYZ") == "XY"


@override_settings(SECRET_KEY="test-secret")
class TestClientHashFor:
    def test_client_hash_for_where_same_ip_same_day_should_be_stable(self):
        # Act / Assert
        assert client_hash_for("1.2.3.4", date(2026, 10, 13)) == client_hash_for("1.2.3.4", date(2026, 10, 13))

    def test_client_hash_for_where_different_day_should_differ(self):
        # Act / Assert
        assert client_hash_for("1.2.3.4", date(2026, 10, 13)) != client_hash_for("1.2.3.4", date(2026, 10, 14))

    def test_client_hash_for_where_hashed_should_not_contain_ip(self):
        # Act
        digest = client_hash_for("2a02:9b0:4039::1", date(2026, 10, 13))

        # Assert
        assert len(digest) == 64
        assert "2a02" not in digest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/usage_tracking/tests/test_download_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: ... download_paths`.

- [ ] **Step 3: Implement**

`apps/usage_tracking/services/download_paths.py`:

```python
"""Maps Cloudflare request paths for asset files to (asset, file kind, surah/version).

Path shapes come from `apps/core/uploads.py`, served under `/media/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import hmac
import re

from django.conf import settings

from apps.usage_tracking.models import AssetDownloadFileKind, AssetDownloadStatusClass

# GraphQL `clientRequestPath_like` filter covering every asset file; the parser drops
# thumbnails/previews that also live under this prefix.
ASSET_PATH_LIKE = "/media/uploads/assets/%"

_SURAH_RE = re.compile(r"^/media/uploads/assets/(?P<asset_id>\d+)/recitations/(?P<surah>\d{3})\.[A-Za-z0-9]+$")
_AYAH_RE = re.compile(
    r"^/media/uploads/assets/(?P<asset_id>\d+)/recitations/\d+/(?P<surah>\d{3})/ayah_\d{3}\.[A-Za-z0-9]+$"
)
_VERSION_RE = re.compile(r"^/media/uploads/assets/(?P<asset_id>\d+)/versions/(?P<version>[^/]+)/[^/]+$")

_UNKNOWN_COUNTRY = "XX"


@dataclass(frozen=True, slots=True)
class DownloadFile:
    asset_id: int
    file_kind: str
    surah: int | None
    asset_version_id: int | None


def parse_download_path(path: str) -> DownloadFile | None:
    if match := _SURAH_RE.match(path):
        return DownloadFile(int(match["asset_id"]), AssetDownloadFileKind.SURAH, int(match["surah"]), None)
    if match := _AYAH_RE.match(path):
        return DownloadFile(int(match["asset_id"]), AssetDownloadFileKind.AYAH, int(match["surah"]), None)
    if match := _VERSION_RE.match(path):
        version = match["version"]
        # `versions/tmp-xxxx/` paths were uploaded before the version row had a pk.
        version_id = int(version) if version.isdigit() else None
        return DownloadFile(int(match["asset_id"]), AssetDownloadFileKind.VERSION, None, version_id)
    return None


def status_class_for(status: int) -> str:
    if status == 200:
        return AssetDownloadStatusClass.FULL
    if status == 206:
        return AssetDownloadStatusClass.PARTIAL
    return AssetDownloadStatusClass.OTHER


def normalize_country(value: str | None) -> str:
    return (value or _UNKNOWN_COUNTRY)[:2].upper()


def client_hash_for(ip: str, day: date) -> str:
    """Pseudonymous client id that cannot be linked across UTC days."""
    key = f"{settings.SECRET_KEY}:{day.isoformat()}".encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_download_paths.py -q`
Expected: 12 passed.

---

### Task 3: Cloudflare client and response mapping

**Files:**
- Create: `apps/usage_tracking/services/cf_downloads_client.py`
- Test: `apps/usage_tracking/tests/test_cf_downloads_client.py`

**Interfaces:**
- Consumes: `CF_GRAPHQL_URL`, `CloudflareGraphQLError` from `apps.usage_tracking.services.cf_analytics_client`; `ASSET_PATH_LIKE` from Task 2.
- Produces:
  - `class CFDownloadEvent(TypedDict)`: `datetime: str`, `rayName: str`, `clientRequestPath: str`, `clientCountryName: str`, `edgeResponseStatus: int`, `clientIP: str`
  - `class CFDownloadTotal(TypedDict)`: `count: int`, `avg: {"sampleInterval": float}`, `sum: {"edgeResponseBytes": int}`, `dimensions: {"clientRequestPath": str, "clientCountryName": str, "edgeResponseStatus": int}`
  - `@dataclass(frozen=True, slots=True) class DatasetLimits: max_page_size: int; not_older_than: timedelta`
  - `class CloudflareDownloadsClient(zone_tag: str, api_token: str, hostname: str)` with `fetch_limits() -> DatasetLimits`, `fetch_events(start: datetime, end: datetime, limit: int) -> list[CFDownloadEvent]`, `fetch_totals(start: datetime, end: datetime, limit: int) -> list[CFDownloadTotal]`. `start` inclusive, `end` exclusive, both UTC.

- [ ] **Step 1: Write the failing tests**

`apps/usage_tracking/tests/test_cf_downloads_client.py`:

```python
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from apps.usage_tracking.services import cf_downloads_client
from apps.usage_tracking.services.cf_analytics_client import CloudflareGraphQLError
from apps.usage_tracking.services.cf_downloads_client import CloudflareDownloadsClient, DatasetLimits

_START = datetime(2026, 10, 13, 10, tzinfo=UTC)
_END = datetime(2026, 10, 13, 11, tzinfo=UTC)

# Shapes recorded from production on 2026-10-13 (IPs replaced).
_EVENT = {
    "clientCountryName": "SA",
    "clientIP": "203.0.113.7",
    "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
    "datetime": "2026-10-13T10:00:18Z",
    "edgeResponseStatus": 200,
    "rayName": "a49d7f1abc4ee1e0",
}
_TOTAL = {
    "count": 4,
    "avg": {"sampleInterval": 1},
    "sum": {"edgeResponseBytes": 29797257},
    "dimensions": {
        "clientCountryName": "SA",
        "clientRequestPath": "/media/uploads/assets/14/recitations/035.mp3",
        "edgeResponseStatus": 206,
    },
}


def _response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def _zone_payload(**zone: object) -> dict:
    return {"data": {"viewer": {"zones": [zone]}}}


class TestCloudflareDownloadsClient:
    def setup_method(self):
        self.client = CloudflareDownloadsClient(zone_tag="zone-1", api_token="token-1", hostname="cdn.example.com")

    def test_fetch_events_where_ok_should_send_filters_and_return_rows(self):
        # Arrange
        with patch.object(
            cf_downloads_client.requests,
            cf_downloads_client.requests.post.__name__,
            return_value=_response(_zone_payload(httpRequestsAdaptive=[_EVENT])),
        ) as post:
            # Act
            rows = self.client.fetch_events(_START, _END, limit=10000)

        # Assert
        assert rows == [_EVENT]
        body = post.call_args.kwargs["json"]
        assert body["variables"] == {
            "zoneTag": "zone-1",
            "start": "2026-10-13T10:00:00Z",
            "end": "2026-10-13T11:00:00Z",
            "hostname": "cdn.example.com",
            "pathLike": "/media/uploads/assets/%",
            "limit": 10000,
        }
        assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer token-1"}

    def test_fetch_totals_where_ok_should_return_rows(self):
        # Arrange
        with patch.object(
            cf_downloads_client.requests,
            cf_downloads_client.requests.post.__name__,
            return_value=_response(_zone_payload(httpRequestsAdaptiveGroups=[_TOTAL])),
        ):
            # Act
            rows = self.client.fetch_totals(_START, _END, limit=10000)

        # Assert
        assert rows == [_TOTAL]

    def test_fetch_limits_where_ok_should_parse_settings(self):
        # Arrange
        payload = _zone_payload(
            settings={"httpRequestsAdaptive": {"maxPageSize": 10000, "notOlderThan": 2678400}}
        )
        with patch.object(
            cf_downloads_client.requests, cf_downloads_client.requests.post.__name__, return_value=_response(payload)
        ):
            # Act
            limits = self.client.fetch_limits()

        # Assert
        assert limits == DatasetLimits(max_page_size=10000, not_older_than=timedelta(days=31))

    def test_fetch_events_where_graphql_errors_should_raise(self):
        # Arrange
        payload = {"data": None, "errors": [{"message": 'unknown field "x"'}]}
        with (
            patch.object(
                cf_downloads_client.requests,
                cf_downloads_client.requests.post.__name__,
                return_value=_response(payload),
            ),
            pytest.raises(CloudflareGraphQLError),
        ):
            # Act
            self.client.fetch_events(_START, _END, limit=10000)

    def test_fetch_events_where_zone_not_matched_should_raise(self):
        # Arrange
        payload = {"data": {"viewer": {"zones": []}}}
        with (
            patch.object(
                cf_downloads_client.requests,
                cf_downloads_client.requests.post.__name__,
                return_value=_response(payload),
            ),
            pytest.raises(CloudflareGraphQLError),
        ):
            # Act
            self.client.fetch_events(_START, _END, limit=10000)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/usage_tracking/tests/test_cf_downloads_client.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`apps/usage_tracking/services/cf_downloads_client.py`:

```python
"""Cloudflare GraphQL Analytics client for per-request asset download data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, TypedDict

import requests

from apps.usage_tracking.services.cf_analytics_client import CF_GRAPHQL_URL, CloudflareGraphQLError
from apps.usage_tracking.services.download_paths import ASSET_PATH_LIKE

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 30

_FILTER = """
          datetime_geq: $start
          datetime_lt: $end
          clientRequestHTTPHost: $hostname
          clientRequestPath_like: $pathLike
          requestSource: "eyeball"
"""

_EVENTS_QUERY = f"""
query AssetDownloadEvents($zoneTag: String!, $start: Time!, $end: Time!, $hostname: String!, $pathLike: String!, $limit: Int!) {{
  viewer {{
    zones(filter: {{ zoneTag: $zoneTag }}) {{
      httpRequestsAdaptive(limit: $limit, filter: {{ {_FILTER} }}, orderBy: [datetime_ASC]) {{
        datetime
        rayName
        clientRequestPath
        clientCountryName
        edgeResponseStatus
        clientIP
      }}
    }}
  }}
}}
"""

_TOTALS_QUERY = f"""
query AssetDownloadTotals($zoneTag: String!, $start: Time!, $end: Time!, $hostname: String!, $pathLike: String!, $limit: Int!) {{
  viewer {{
    zones(filter: {{ zoneTag: $zoneTag }}) {{
      httpRequestsAdaptiveGroups(limit: $limit, filter: {{ {_FILTER} }}) {{
        count
        avg {{ sampleInterval }}
        sum {{ edgeResponseBytes }}
        dimensions {{
          clientRequestPath
          clientCountryName
          edgeResponseStatus
        }}
      }}
    }}
  }}
}}
"""

_LIMITS_QUERY = """
query AssetDownloadLimits($zoneTag: String!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      settings { httpRequestsAdaptive { maxPageSize notOlderThan } }
    }
  }
}
"""


class CFDownloadEvent(TypedDict):
    datetime: str
    rayName: str
    clientRequestPath: str
    clientCountryName: str
    edgeResponseStatus: int
    clientIP: str


class CFDownloadTotalDimensions(TypedDict):
    clientRequestPath: str
    clientCountryName: str
    edgeResponseStatus: int


class CFDownloadTotal(TypedDict):
    count: int
    avg: dict[str, float]
    sum: dict[str, int]
    dimensions: CFDownloadTotalDimensions


@dataclass(frozen=True, slots=True)
class DatasetLimits:
    max_page_size: int
    not_older_than: timedelta


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class CloudflareDownloadsClient:
    """Reads asset-file requests for one hostname. `start` is inclusive, `end` exclusive (UTC)."""

    def __init__(self, zone_tag: str, api_token: str, hostname: str) -> None:
        self._zone_tag = zone_tag
        self._api_token = api_token
        self._hostname = hostname

    def fetch_limits(self) -> DatasetLimits:
        zone = self._zone(_LIMITS_QUERY, {"zoneTag": self._zone_tag})
        dataset = zone["settings"]["httpRequestsAdaptive"]
        return DatasetLimits(
            max_page_size=int(dataset["maxPageSize"]),
            not_older_than=timedelta(seconds=int(dataset["notOlderThan"])),
        )

    def fetch_events(self, start: datetime, end: datetime, limit: int) -> list[CFDownloadEvent]:
        return self._zone(_EVENTS_QUERY, self._range_variables(start, end, limit))["httpRequestsAdaptive"]

    def fetch_totals(self, start: datetime, end: datetime, limit: int) -> list[CFDownloadTotal]:
        return self._zone(_TOTALS_QUERY, self._range_variables(start, end, limit))["httpRequestsAdaptiveGroups"]

    def _range_variables(self, start: datetime, end: datetime, limit: int) -> dict[str, Any]:
        return {
            "zoneTag": self._zone_tag,
            "start": _format_time(start),
            "end": _format_time(end),
            "hostname": self._hostname,
            "pathLike": ASSET_PATH_LIKE,
            "limit": limit,
        }

    def _zone(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            CF_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers={"Authorization": f"Bearer {self._api_token}"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        if payload.get("errors"):
            raise CloudflareGraphQLError(str(payload["errors"]))
        zones = ((payload.get("data") or {}).get("viewer") or {}).get("zones") or []
        if not zones:
            raise CloudflareGraphQLError(f"no zone matched zoneTag={self._zone_tag} (check CF_ZONE_ID/token scope)")
        return zones[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_cf_downloads_client.py -q`
Expected: 5 passed.

---

### Task 4: Repository — replace an hour, plays, daily rebuild, state

**Files:**
- Create: `apps/usage_tracking/repositories/asset_downloads.py`
- Test: `apps/usage_tracking/tests/test_asset_downloads_repository.py`

**Interfaces:**
- Consumes: models (Task 1), `DownloadFile` (Task 2).
- Produces:
  - `SYNC_KEY = "cf_asset_downloads"`
  - `@dataclass(frozen=True, slots=True) class DownloadEventRow: ray_id: str; occurred_at: datetime; file: DownloadFile; country: str; status_class: str; client_hash: str`
  - `@dataclass(frozen=True, slots=True) class DownloadTotalRow: file: DownloadFile; country: str; status_class: str; requests: int; bytes: int`
  - `class AssetDownloadRepository` with:
    - `get_watermark() -> datetime | None`
    - `try_lock() -> bool`, `unlock() -> None`
    - `replace_hour(hour: datetime, events: list[DownloadEventRow], totals: list[DownloadTotalRow], play_window: timedelta) -> None`
    - `record_run(now: datetime, error: str) -> None`
    - `purge_events_before(cutoff: datetime) -> int`

- [ ] **Step 1: Write the failing tests**

`apps/usage_tracking/tests/test_asset_downloads_repository.py`:

```python
from datetime import UTC, date, datetime, timedelta

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
    UsageSyncState,
)
from apps.usage_tracking.repositories.asset_downloads import (
    AssetDownloadRepository,
    DownloadEventRow,
    DownloadTotalRow,
)
from apps.usage_tracking.services.download_paths import DownloadFile

H10 = datetime(2026, 10, 13, 10, tzinfo=UTC)
H11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
WINDOW = timedelta(minutes=5)
SURAH_91 = DownloadFile(13, AssetDownloadFileKind.SURAH, 91, None)
FULL = AssetDownloadStatusClass.FULL
PARTIAL = AssetDownloadStatusClass.PARTIAL


def _event(ray: str, at: datetime, client: str = "c1", status: str = FULL, file: DownloadFile = SURAH_91):
    return DownloadEventRow(ray, at, file, "SA", status, client * 32)


def _total(requests: int, bytes_: int, status: str = FULL, file: DownloadFile = SURAH_91) -> DownloadTotalRow:
    return DownloadTotalRow(file, "SA", status, requests, bytes_)


class TestReplaceHour(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = AssetDownloadRepository()

    def test_replace_hour_where_200_and_206_pair_should_count_one_play(self):
        # Arrange
        events = [_event("r1", H10 + timedelta(seconds=1)), _event("r2", H10 + timedelta(seconds=2), status=PARTIAL)]
        totals = [_total(1, 100), _total(1, 50, status=PARTIAL)]

        # Act
        self.repo.replace_hour(H10, events, totals, WINDOW)

        # Assert
        rows = {r.status_class: r for r in AssetDownloadHourly.objects.filter(hour=H10)}
        assert rows[FULL].requests == 1 and rows[FULL].bytes == 100 and rows[FULL].plays == 1
        assert rows[PARTIAL].requests == 1 and rows[PARTIAL].plays == 0
        assert AssetDownloadEvent.objects.count() == 2

    def test_replace_hour_where_gap_over_window_should_count_two_plays(self):
        # Arrange
        events = [_event("r1", H10 + timedelta(minutes=1)), _event("r2", H10 + timedelta(minutes=7))]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 200)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 2

    def test_replace_hour_where_different_clients_should_count_separate_plays(self):
        # Arrange
        events = [_event("r1", H10, client="a"), _event("r2", H10 + timedelta(seconds=5), client="b")]

        # Act
        self.repo.replace_hour(H10, events, [_total(2, 200)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 2

    def test_replace_hour_where_play_continues_from_previous_hour_should_not_recount(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H11 - timedelta(minutes=2))], [_total(1, 100)], WINDOW)

        # Act
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=1))], [_total(1, 100)], WINDOW)

        # Assert
        assert AssetDownloadHourly.objects.get(hour=H10).plays == 1
        assert AssetDownloadHourly.objects.get(hour=H11).plays == 0

    def test_replace_hour_where_run_twice_with_changed_data_should_replace_not_add(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H10)], [_total(1, 100)], WINDOW)

        # Act
        self.repo.replace_hour(H10, [_event("r1", H10), _event("r9", H10 + timedelta(minutes=30))], [_total(2, 300)], WINDOW)

        # Assert
        row = AssetDownloadHourly.objects.get(hour=H10)
        assert (row.requests, row.bytes, row.plays) == (2, 300, 2)
        assert AssetDownloadEvent.objects.count() == 2

    def test_replace_hour_where_hours_written_should_rebuild_daily_as_sum(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("r1", H10)], [_total(1, 100)], WINDOW)

        # Act
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=30))], [_total(3, 300)], WINDOW)
        self.repo.replace_hour(H11, [_event("r2", H11 + timedelta(minutes=30))], [_total(4, 400)], WINDOW)

        # Assert
        daily = AssetDownloadDaily.objects.get(day=date(2026, 10, 13))
        assert (daily.requests, daily.bytes, daily.plays) == (5, 500, 2)

    def test_replace_hour_where_written_should_advance_watermark_never_backwards(self):
        # Arrange
        self.repo.replace_hour(H11, [], [], WINDOW)

        # Act
        self.repo.replace_hour(H10, [], [], WINDOW)

        # Assert
        assert self.repo.get_watermark() == H11 + timedelta(hours=1)


class TestStateAndMaintenance(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.repo = AssetDownloadRepository()

    def test_try_lock_where_free_should_acquire_and_release(self):
        # Act
        first = self.repo.try_lock()
        self.repo.unlock()

        # Assert
        assert first is True

    def test_record_run_where_error_should_store_it(self):
        # Act
        self.repo.record_run(H11, "boom")

        # Assert
        state = UsageSyncState.objects.get(key="cf_asset_downloads")
        assert (state.last_run_at, state.last_error) == (H11, "boom")

    def test_purge_events_before_where_old_events_should_delete_only_those(self):
        # Arrange
        self.repo.replace_hour(H10, [_event("old", H10), _event("new", H11 - timedelta(seconds=1))], [], WINDOW)

        # Act
        deleted = self.repo.purge_events_before(H10 + timedelta(minutes=30))

        # Assert
        assert deleted == 1
        assert list(AssetDownloadEvent.objects.values_list("ray_id", flat=True)) == ["new"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/usage_tracking/tests/test_asset_downloads_repository.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`apps/usage_tracking/repositories/asset_downloads.py`:

```python
"""Persistence for asset download statistics: events, rollups and sync state."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from django.db import connection, transaction
from django.db.models import Sum

from apps.usage_tracking.models import (
    ROLLUP_DIMENSIONS,
    AssetDownloadDaily,
    AssetDownloadEvent,
    AssetDownloadHourly,
    UsageSyncState,
)
from apps.usage_tracking.services.download_paths import DownloadFile

SYNC_KEY = "cf_asset_downloads"
# Arbitrary constant identifying this job's Postgres advisory lock.
_ADVISORY_LOCK_ID = 7_340_212_026

DimensionKey = tuple[int, str, int | None, int | None, str, str]


@dataclass(frozen=True, slots=True)
class DownloadEventRow:
    ray_id: str
    occurred_at: datetime
    file: DownloadFile
    country: str
    status_class: str
    client_hash: str


@dataclass(frozen=True, slots=True)
class DownloadTotalRow:
    file: DownloadFile
    country: str
    status_class: str
    requests: int
    bytes: int


def _key(file: DownloadFile, country: str, status_class: str) -> DimensionKey:
    return (file.asset_id, file.file_kind, file.surah, file.asset_version_id, country, status_class)


# A request starts a play unless the same client requested the same file within the
# window before it. The CTE reads `window` of context before the hour so a play that
# began in the previous hour is not counted again.
_PLAYS_SQL = """
WITH ordered AS (
    SELECT occurred_at, asset_id, file_kind, surah, asset_version_id, country, status_class,
           LAG(occurred_at) OVER (
               PARTITION BY client_hash, asset_id, file_kind, surah, asset_version_id
               ORDER BY occurred_at, ray_id
           ) AS previous_at
    FROM {table}
    WHERE occurred_at >= %(context_start)s AND occurred_at < %(end)s
)
SELECT asset_id, file_kind, surah, asset_version_id, country, status_class, COUNT(*)
FROM ordered
WHERE occurred_at >= %(start)s AND (previous_at IS NULL OR occurred_at - previous_at > %(window)s)
GROUP BY asset_id, file_kind, surah, asset_version_id, country, status_class
"""


class AssetDownloadRepository:
    def get_watermark(self) -> datetime | None:
        return UsageSyncState.objects.filter(key=SYNC_KEY).values_list("watermark", flat=True).first()

    def try_lock(self) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", [_ADVISORY_LOCK_ID])
            return bool(cursor.fetchone()[0])

    def unlock(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [_ADVISORY_LOCK_ID])

    def replace_hour(
        self,
        hour: datetime,
        events: list[DownloadEventRow],
        totals: list[DownloadTotalRow],
        play_window: timedelta,
    ) -> None:
        """Replace everything stored for `hour` and advance the watermark, atomically."""
        end = hour + timedelta(hours=1)
        with transaction.atomic():
            AssetDownloadEvent.objects.filter(occurred_at__gte=hour, occurred_at__lt=end).delete()
            AssetDownloadEvent.objects.bulk_create(
                [
                    AssetDownloadEvent(
                        ray_id=event.ray_id,
                        occurred_at=event.occurred_at,
                        asset_id=event.file.asset_id,
                        file_kind=event.file.file_kind,
                        surah=event.file.surah,
                        asset_version_id=event.file.asset_version_id,
                        country=event.country,
                        status_class=event.status_class,
                        client_hash=event.client_hash,
                    )
                    for event in events
                ],
                ignore_conflicts=True,
            )
            self._rebuild_hourly(hour, totals, play_window)
            self._rebuild_daily(hour)
            self._advance_watermark(end)

    def record_run(self, now: datetime, error: str) -> None:
        UsageSyncState.objects.update_or_create(key=SYNC_KEY, defaults={"last_run_at": now, "last_error": error})

    def purge_events_before(self, cutoff: datetime) -> int:
        deleted, _ = AssetDownloadEvent.objects.filter(occurred_at__lt=cutoff).delete()
        return deleted

    def _plays(self, hour: datetime, play_window: timedelta) -> dict[DimensionKey, int]:
        params = {
            "context_start": hour - play_window,
            "start": hour,
            "end": hour + timedelta(hours=1),
            "window": play_window,
        }
        with connection.cursor() as cursor:
            cursor.execute(_PLAYS_SQL.format(table=AssetDownloadEvent._meta.db_table), params)
            return {tuple(row[:6]): int(row[6]) for row in cursor.fetchall()}

    def _rebuild_hourly(self, hour: datetime, totals: list[DownloadTotalRow], play_window: timedelta) -> None:
        metrics: dict[DimensionKey, list[int]] = defaultdict(lambda: [0, 0, 0])
        for total in totals:
            entry = metrics[_key(total.file, total.country, total.status_class)]
            entry[0] += total.requests
            entry[1] += total.bytes
        for key, plays in self._plays(hour, play_window).items():
            metrics[key][2] += plays

        AssetDownloadHourly.objects.filter(hour=hour).delete()
        AssetDownloadHourly.objects.bulk_create(
            [
                AssetDownloadHourly(
                    hour=hour,
                    **dict(zip(ROLLUP_DIMENSIONS, key, strict=True)),
                    requests=requests,
                    bytes=bytes_,
                    plays=plays,
                )
                for key, (requests, bytes_, plays) in metrics.items()
            ]
        )

    def _rebuild_daily(self, hour: datetime) -> None:
        day = hour.astimezone(UTC).date()
        day_start = datetime.combine(day, time.min, tzinfo=UTC)
        rows = (
            AssetDownloadHourly.objects.filter(hour__gte=day_start, hour__lt=day_start + timedelta(days=1))
            .values(*ROLLUP_DIMENSIONS)
            .annotate(total_requests=Sum("requests"), total_bytes=Sum("bytes"), total_plays=Sum("plays"))
        )
        AssetDownloadDaily.objects.filter(day=day).delete()
        AssetDownloadDaily.objects.bulk_create(
            [
                AssetDownloadDaily(
                    day=day,
                    **{dimension: row[dimension] for dimension in ROLLUP_DIMENSIONS},
                    requests=row["total_requests"],
                    bytes=row["total_bytes"],
                    plays=row["total_plays"],
                )
                for row in rows
            ]
        )

    def _advance_watermark(self, candidate: datetime) -> None:
        state, _ = UsageSyncState.objects.select_for_update().get_or_create(key=SYNC_KEY)
        if state.watermark is None or candidate > state.watermark:
            state.watermark = candidate
            state.save(update_fields=["watermark", "updated_at"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_asset_downloads_repository.py -q`
Expected: 10 passed.

---

### Task 5: Sync service, task and beat schedule

**Files:**
- Create: `apps/usage_tracking/services/asset_download_sync.py`
- Modify: `apps/usage_tracking/tasks.py` (append task; add import)
- Modify: `config/celery.py` (beat entry after `sync-audio-usage`)
- Test: `apps/usage_tracking/tests/test_asset_download_sync.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - `plan_hours(now: datetime, watermark: datetime | None, oldest_allowed: datetime, *, lag_minutes: int, refresh_hours: int, max_slices: int) -> list[datetime]`
  - `fetch_complete(fetch: Callable[[datetime, datetime, int], list[T]], start: datetime, end: datetime, limit: int) -> tuple[list[T], bool]` (bool = still truncated at the 5-minute floor)
  - `build_event_rows(events: list[CFDownloadEvent]) -> tuple[list[DownloadEventRow], int]` (int = unmatched paths)
  - `build_total_rows(totals: list[CFDownloadTotal]) -> tuple[list[DownloadTotalRow], bool]` (bool = sampled)
  - `@dataclass(frozen=True, slots=True) class SyncResult: hours_synced: int; error: str`
  - `sync_asset_downloads(now: datetime | None = None) -> SyncResult`
  - Celery task `apps.usage_tracking.tasks.sync_asset_downloads_task`

- [ ] **Step 1: Write the failing tests**

`apps/usage_tracking/tests/test_asset_download_sync.py`:

```python
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from django.test import override_settings

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import AssetDownloadEvent, AssetDownloadHourly, UsageSyncState
from apps.usage_tracking.repositories.asset_downloads import AssetDownloadRepository
from apps.usage_tracking.services import asset_download_sync
from apps.usage_tracking.services.asset_download_sync import (
    build_event_rows,
    build_total_rows,
    fetch_complete,
    plan_hours,
    sync_asset_downloads,
)
from apps.usage_tracking.services.cf_downloads_client import CloudflareDownloadsClient, DatasetLimits

NOW = datetime(2026, 10, 13, 12, 20, tzinfo=UTC)  # last complete hour with 15 min lag: 11:00-12:00
OLDEST = datetime(2026, 9, 12, 13, tzinfo=UTC)
_PLAN = {"lag_minutes": 15, "refresh_hours": 2, "max_slices": 24}


def _hours(*values: int) -> list[datetime]:
    return [datetime(2026, 10, 13, value, tzinfo=UTC) for value in values]


class TestPlanHours:
    def test_plan_hours_where_watermark_current_should_refresh_last_two_hours(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 12, tzinfo=UTC), OLDEST, **_PLAN)

        # Assert
        assert hours == _hours(10, 11)

    def test_plan_hours_where_watermark_behind_should_cover_gap(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 6, tzinfo=UTC), OLDEST, **_PLAN)

        # Assert
        assert hours == _hours(6, 7, 8, 9, 10, 11)

    def test_plan_hours_where_lag_not_elapsed_should_exclude_current_hour(self):
        # Act
        hours = plan_hours(datetime(2026, 10, 13, 12, 10, tzinfo=UTC), None, datetime(2026, 10, 13, 10, tzinfo=UTC), **_PLAN)

        # Assert
        assert hours == _hours(10)

    def test_plan_hours_where_backlog_exceeds_cap_should_take_oldest_first(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 10, 13, 0, tzinfo=UTC), OLDEST, **{**_PLAN, "max_slices": 3})

        # Assert
        assert hours == _hours(0, 1, 2)

    def test_plan_hours_where_watermark_older_than_retention_should_start_at_oldest_allowed(self):
        # Act
        hours = plan_hours(NOW, datetime(2026, 9, 1, tzinfo=UTC), OLDEST, **{**_PLAN, "max_slices": 2})

        # Assert
        assert hours == [OLDEST, OLDEST + timedelta(hours=1)]


class TestFetchComplete:
    def test_fetch_complete_where_page_full_should_split_halves_without_overlap(self):
        # Arrange
        calls: list[tuple[datetime, datetime]] = []

        def fetch(start: datetime, end: datetime, limit: int) -> list[int]:
            calls.append((start, end))
            return [1, 2] if end - start == timedelta(hours=1) else [1]

        start = datetime(2026, 10, 13, 10, tzinfo=UTC)

        # Act
        rows, truncated = fetch_complete(fetch, start, start + timedelta(hours=1), limit=2)

        # Assert
        assert (rows, truncated) == ([1, 1], False)
        assert calls[1] == (start, start + timedelta(minutes=30))
        assert calls[2] == (start + timedelta(minutes=30), start + timedelta(hours=1))

    def test_fetch_complete_where_full_at_floor_should_report_truncated(self):
        # Arrange
        start = datetime(2026, 10, 13, 10, tzinfo=UTC)

        # Act
        _, truncated = fetch_complete(lambda s, e, limit: [0] * limit, start, start + timedelta(minutes=5), limit=3)

        # Assert
        assert truncated is True


@override_settings(SECRET_KEY="test-secret")
class TestBuildRows:
    def test_build_event_rows_where_mixed_paths_should_skip_unmatched_and_normalize(self):
        # Arrange
        events = [
            {
                "datetime": "2026-10-13T10:00:18Z",
                "rayName": "r1",
                "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
                "clientCountryName": "",
                "edgeResponseStatus": 206,
                "clientIP": "203.0.113.7",
            },
            {
                "datetime": "2026-10-13T10:00:19Z",
                "rayName": "r2",
                "clientRequestPath": "/media/uploads/assets/13/cover.png",
                "clientCountryName": "SA",
                "edgeResponseStatus": 200,
                "clientIP": "203.0.113.7",
            },
        ]

        # Act
        rows, unmatched = build_event_rows(events)

        # Assert
        assert unmatched == 1
        assert len(rows) == 1
        assert rows[0].occurred_at == datetime(2026, 10, 13, 10, 0, 18, tzinfo=UTC)
        assert (rows[0].country, rows[0].status_class) == ("XX", "partial")
        assert "203.0.113.7" not in rows[0].client_hash

    def test_build_total_rows_where_sample_interval_above_one_should_flag_sampled(self):
        # Arrange
        totals = [
            {
                "count": 4,
                "avg": {"sampleInterval": 10},
                "sum": {"edgeResponseBytes": 40},
                "dimensions": {
                    "clientRequestPath": "/media/uploads/assets/14/recitations/035.mp3",
                    "clientCountryName": "SA",
                    "edgeResponseStatus": 200,
                },
            }
        ]

        # Act
        rows, sampled = build_total_rows(totals)

        # Assert
        assert sampled is True
        assert (rows[0].requests, rows[0].bytes) == (4, 40)


_SYNC_SETTINGS = {
    "ENABLE_ASSET_DOWNLOAD_SYNC": True,
    "CF_ZONE_ID": "zone-1",
    "CF_API_TOKEN": "token-1",
    "CF_R2_CUSTOM_DOMAIN": "cdn.example.com",
    "SECRET_KEY": "test-secret",
}


def _cf_event(ray: str, at: str) -> dict:
    return {
        "datetime": at,
        "rayName": ray,
        "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
        "clientCountryName": "SA",
        "edgeResponseStatus": 200,
        "clientIP": "203.0.113.7",
    }


def _cf_total(count: int) -> dict:
    return {
        "count": count,
        "avg": {"sampleInterval": 1},
        "sum": {"edgeResponseBytes": count * 100},
        "dimensions": {
            "clientRequestPath": "/media/uploads/assets/13/recitations/091.mp3",
            "clientCountryName": "SA",
            "edgeResponseStatus": 200,
        },
    }


@override_settings(**_SYNC_SETTINGS)
class TestSyncAssetDownloads(BaseTestCase):
    def _patch_client(self, events_by_hour: dict[datetime, list[dict]], fail_hour: datetime | None = None):
        def fetch_events(start: datetime, end: datetime, limit: int) -> list[dict]:
            if start == fail_hour:
                raise RuntimeError("cloudflare down")
            return events_by_hour.get(start, [])

        def fetch_totals(start: datetime, end: datetime, limit: int) -> list[dict]:
            return [_cf_total(len(events_by_hour[start]))] if events_by_hour.get(start) else []

        client = MagicMock(spec=CloudflareDownloadsClient)
        client.fetch_limits.return_value = DatasetLimits(max_page_size=10000, not_older_than=timedelta(hours=4))
        client.fetch_events.side_effect = fetch_events
        client.fetch_totals.side_effect = fetch_totals
        return patch.object(asset_download_sync, asset_download_sync._build_client.__name__, return_value=client)

    @override_settings(ENABLE_ASSET_DOWNLOAD_SYNC=False)
    def test_sync_asset_downloads_where_disabled_should_do_nothing(self):
        # Act
        result = sync_asset_downloads(NOW)

        # Assert
        assert result.hours_synced == 0
        assert not UsageSyncState.objects.exists()

    def test_sync_asset_downloads_where_first_run_should_backfill_retained_hours(self):
        # Arrange
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        with self._patch_client({h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert  (oldest allowed = ceil(12:20 - 4h) + 1h = 10:00 → hours 10, 11)
        assert (result.hours_synced, result.error) == (2, "")
        assert AssetDownloadRepository().get_watermark() == datetime(2026, 10, 13, 12, tzinfo=UTC)
        assert AssetDownloadHourly.objects.get(hour=h11).plays == 1

    def test_sync_asset_downloads_where_rerun_should_not_duplicate(self):
        # Arrange
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        data = {h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}
        with self._patch_client(data):
            sync_asset_downloads(NOW)

            # Act
            sync_asset_downloads(NOW)

        # Assert
        assert AssetDownloadEvent.objects.count() == 1
        assert AssetDownloadHourly.objects.get(hour=h11).requests == 1

    def test_sync_asset_downloads_where_hour_fails_should_keep_watermark_and_record_error(self):
        # Arrange
        h10 = datetime(2026, 10, 13, 10, tzinfo=UTC)
        h11 = datetime(2026, 10, 13, 11, tzinfo=UTC)
        with self._patch_client({h11: [_cf_event("r1", "2026-10-13T11:05:00Z")]}, fail_hour=h11):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert
        assert result.hours_synced == 1
        assert "cloudflare down" in result.error
        assert AssetDownloadRepository().get_watermark() == h11
        assert UsageSyncState.objects.get().last_error == result.error
        # hour 10 committed; hour 11 rolled back
        assert AssetDownloadHourly.objects.filter(hour=h10).count() == 0  # no data that hour
        assert not AssetDownloadHourly.objects.filter(hour=h11).exists()

    def test_sync_asset_downloads_where_lock_held_should_skip(self):
        # Arrange
        with (
            patch.object(AssetDownloadRepository, AssetDownloadRepository.try_lock.__name__, return_value=False),
            self._patch_client({}) as build_client,
        ):
            # Act
            result = sync_asset_downloads(NOW)

        # Assert
        assert result.hours_synced == 0
        build_client.assert_not_called()

    @override_settings(ASSET_DOWNLOAD_EVENT_RETENTION_DAYS=1)
    def test_sync_asset_downloads_where_retention_set_should_purge_old_events(self):
        # Arrange
        AssetDownloadEvent.objects.create(
            ray_id="ancient",
            occurred_at=NOW - timedelta(days=3),
            asset_id=1,
            file_kind="surah",
            surah=1,
            country="SA",
            status_class="full",
            client_hash="x" * 64,
        )
        with self._patch_client({}):
            # Act
            sync_asset_downloads(NOW)

        # Assert
        assert not AssetDownloadEvent.objects.filter(ray_id="ancient").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest apps/usage_tracking/tests/test_asset_download_sync.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the service**

`apps/usage_tracking/services/asset_download_sync.py`:

```python
"""Hourly import of asset download data from Cloudflare into events and rollups.

Each UTC hour is replaced as a whole (events, hourly rows, daily rows) and the
watermark only advances after an hour commits, so re-runs never duplicate and a
missed or failed run is picked up by the next one, within Cloudflare's retention.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import TypeVar

from django.conf import settings

from apps.usage_tracking.repositories.asset_downloads import (
    AssetDownloadRepository,
    DownloadEventRow,
    DownloadTotalRow,
)
from apps.usage_tracking.services.cf_downloads_client import (
    CFDownloadEvent,
    CFDownloadTotal,
    CloudflareDownloadsClient,
)
from apps.usage_tracking.services.download_paths import (
    client_hash_for,
    normalize_country,
    parse_download_path,
    status_class_for,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_HOUR = timedelta(hours=1)
_MIN_SPLIT = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class SyncResult:
    hours_synced: int
    error: str


def _floor_hour(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def _ceil_hour(value: datetime) -> datetime:
    floored = _floor_hour(value)
    return floored if floored == value else floored + _HOUR


def plan_hours(
    now: datetime,
    watermark: datetime | None,
    oldest_allowed: datetime,
    *,
    lag_minutes: int,
    refresh_hours: int,
    max_slices: int,
) -> list[datetime]:
    """Hour starts to (re)import, oldest first.

    Covers everything from the watermark (or the oldest retained hour on a first run),
    plus the last `refresh_hours` complete hours to pick up late Cloudflare data.
    """
    end = _floor_hour(now - timedelta(minutes=lag_minutes))  # exclusive: hours ending by now - lag
    refresh_start = end - timedelta(hours=refresh_hours)
    if watermark is None:
        start = oldest_allowed  # first run: backfill everything Cloudflare still retains
    else:
        start = max(min(watermark, refresh_start), oldest_allowed)
    hours: list[datetime] = []
    current = start
    while current + _HOUR <= end and len(hours) < max_slices:
        hours.append(current)
        current += _HOUR
    return hours


def fetch_complete(
    fetch: Callable[[datetime, datetime, int], list[T]], start: datetime, end: datetime, limit: int
) -> tuple[list[T], bool]:
    """Fetch `[start, end)`, halving the range while a page comes back full."""
    rows = fetch(start, end, limit)
    if len(rows) < limit:
        return rows, False
    if end - start <= _MIN_SPLIT:
        return rows, True
    middle = start + (end - start) / 2
    left, left_truncated = fetch_complete(fetch, start, middle, limit)
    right, right_truncated = fetch_complete(fetch, middle, end, limit)
    return left + right, left_truncated or right_truncated


def build_event_rows(events: list[CFDownloadEvent]) -> tuple[list[DownloadEventRow], int]:
    rows: list[DownloadEventRow] = []
    unmatched = 0
    for event in events:
        file = parse_download_path(event["clientRequestPath"])
        if file is None:
            unmatched += 1
            continue
        occurred_at = datetime.fromisoformat(event["datetime"].replace("Z", "+00:00"))
        rows.append(
            DownloadEventRow(
                ray_id=event["rayName"],
                occurred_at=occurred_at,
                file=file,
                country=normalize_country(event["clientCountryName"]),
                status_class=status_class_for(event["edgeResponseStatus"]),
                client_hash=client_hash_for(event["clientIP"] or "", occurred_at.date()),
            )
        )
    return rows, unmatched


def build_total_rows(totals: list[CFDownloadTotal]) -> tuple[list[DownloadTotalRow], bool]:
    rows: list[DownloadTotalRow] = []
    sampled = False
    for total in totals:
        sampled = sampled or total["avg"]["sampleInterval"] > 1
        dimensions = total["dimensions"]
        file = parse_download_path(dimensions["clientRequestPath"])
        if file is None:
            continue
        rows.append(
            DownloadTotalRow(
                file=file,
                country=normalize_country(dimensions["clientCountryName"]),
                status_class=status_class_for(dimensions["edgeResponseStatus"]),
                requests=total["count"],
                bytes=total["sum"]["edgeResponseBytes"],
            )
        )
    return rows, sampled


def _build_client() -> CloudflareDownloadsClient:
    return CloudflareDownloadsClient(
        zone_tag=settings.CF_ZONE_ID, api_token=settings.CF_API_TOKEN, hostname=settings.CF_R2_CUSTOM_DOMAIN
    )


def _sync_hour(
    client: CloudflareDownloadsClient, repo: AssetDownloadRepository, hour: datetime, page_size: int
) -> None:
    end = hour + _HOUR
    raw_events, events_truncated = fetch_complete(client.fetch_events, hour, end, page_size)
    raw_totals, totals_truncated = fetch_complete(client.fetch_totals, hour, end, page_size)
    if events_truncated or totals_truncated:
        logger.error("sync_asset_downloads: hour %s still truncated at the 5-minute floor; stored partial data", hour)
    events, unmatched = build_event_rows(raw_events)
    totals, sampled = build_total_rows(raw_totals)
    if sampled:
        logger.warning("sync_asset_downloads: hour %s is sampled by Cloudflare; plays are approximate", hour)
    repo.replace_hour(hour, events, totals, timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES))
    logger.info(
        "sync_asset_downloads: hour=%s events=%d totals=%d unmatched=%d", hour, len(events), len(totals), unmatched
    )


def sync_asset_downloads(now: datetime | None = None) -> SyncResult:
    if not settings.ENABLE_ASSET_DOWNLOAD_SYNC:
        logger.info("sync_asset_downloads: disabled via ENABLE_ASSET_DOWNLOAD_SYNC; skipping")
        return SyncResult(0, "")
    if not (settings.CF_ZONE_ID and settings.CF_API_TOKEN and settings.CF_R2_CUSTOM_DOMAIN):
        logger.warning("sync_asset_downloads: missing CF_ZONE_ID/CF_API_TOKEN/CF_R2_CUSTOM_DOMAIN; skipping")
        return SyncResult(0, "")

    now = now or datetime.now(UTC)
    repo = AssetDownloadRepository()
    if not repo.try_lock():
        logger.info("sync_asset_downloads: another run holds the lock; skipping")
        return SyncResult(0, "")

    hours_synced = 0
    error = ""
    try:
        client = _build_client()
        limits = client.fetch_limits()
        oldest_allowed = _ceil_hour(now - limits.not_older_than) + _HOUR
        watermark = repo.get_watermark()
        if watermark is not None and watermark < oldest_allowed:
            logger.error(
                "sync_asset_downloads: data lost for [%s, %s) — older than Cloudflare retention",
                watermark,
                oldest_allowed,
            )
        hours = plan_hours(
            now,
            watermark,
            oldest_allowed,
            lag_minutes=settings.ASSET_DOWNLOAD_SYNC_LAG_MINUTES,
            refresh_hours=settings.ASSET_DOWNLOAD_SYNC_REFRESH_HOURS,
            max_slices=settings.ASSET_DOWNLOAD_SYNC_MAX_SLICES_PER_RUN,
        )
        for hour in hours:
            _sync_hour(client, repo, hour, limits.max_page_size)
            hours_synced += 1

        if settings.ASSET_DOWNLOAD_EVENT_RETENTION_DAYS:
            repo.purge_events_before(now - timedelta(days=settings.ASSET_DOWNLOAD_EVENT_RETENTION_DAYS))
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("sync_asset_downloads: run failed after %d hour(s)", hours_synced)
    finally:
        repo.record_run(now, error)
        repo.unlock()

    watermark = repo.get_watermark()
    if watermark is None or watermark < now - timedelta(hours=settings.ASSET_DOWNLOAD_SYNC_STALE_HOURS):
        logger.error("sync_asset_downloads: watermark %s is stale (now=%s)", watermark, now)
    return SyncResult(hours_synced, error)
```

- [ ] **Step 4: Add the Celery task**

In `apps/usage_tracking/tasks.py` add next to the existing service import:

```python
from apps.usage_tracking.services.asset_download_sync import sync_asset_downloads
```

and append:

```python
@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def sync_asset_downloads_task() -> None:
    """Import asset download data from Cloudflare (see `asset_download_sync`).

    No autoretry: failures are recorded on the sync state and the next hourly run
    resumes from the watermark. Re-delivery is safe because each hour is replaced.
    """
    result = sync_asset_downloads()
    logger.info("sync_asset_downloads_task: synced %d hour(s); error=%r", result.hours_synced, result.error)
```

- [ ] **Step 5: Add the beat entry**

In `config/celery.py`, after the `"sync-audio-usage"` entry:

```python
    "sync-asset-downloads": {
        "task": "apps.usage_tracking.tasks.sync_asset_downloads_task",
        # Minute 20: after the 15-minute Cloudflare lag, offset from sync-audio-usage (minute 5).
        "schedule": crontab(minute=20),
    },
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_asset_download_sync.py -q`
Expected: 15 passed.

- [ ] **Step 7: Run the whole app**

Run: `uv run pytest apps/usage_tracking -q`
Expected: all pass.

---

### Task 6: Permission and portal API

**Files:**
- Modify: `apps/core/permissions.py` (after the Access Requests block, ~line 82)
- Modify: `apps/publishers/services/publisher_member_service.py` (`PUBLISHER_MEMBER_GROUP_PERMS`)
- Create: `apps/usage_tracking/api/portal/downloads.py`
- Test: `apps/usage_tracking/tests/test_portal_downloads.py`

**Interfaces:**
- Consumes: models, `SYNC_KEY` (Task 4).
- Produces: `PermissionChoice.PORTAL_READ_USAGE = "portal_read_usage"`; endpoints
  - `GET /portal/usage/downloads/summary/?start_date&end_date[&asset_id][&file_kind]` → `{data_until, total: Metrics, by_file_kind: {surah, ayah, version: Metrics}}`
  - `GET /portal/usage/downloads/timeseries/?...&granularity=hour|day|month[&split_by=file_kind|status_class]` → `{data_until, granularity, series: [{key, points: [{t, ...Metrics}]}]}`
  - `GET /portal/usage/downloads/breakdown/?...&by=asset|surah|country[&limit=10]` → `{data_until, by, items: [{key, label, ...Metrics}]}`
  - `Metrics = {requests_full, requests_partial, requests_other, bytes, plays}`; errors `asset_not_found` (404), `invalid_range` (400), `range_too_large` (400), `permission_denied` (403).

- [ ] **Step 1: Add the permission and grant it**

`apps/core/permissions.py`, after the access-requests entries:

```python
    # Usage statistics
    PORTAL_READ_USAGE = "portal_read_usage", _("Portal - View Usage Statistics")
```

`apps/publishers/services/publisher_member_service.py`, append to `PUBLISHER_MEMBER_GROUP_PERMS`:

```python
    PermissionChoice.PORTAL_READ_USAGE.value,
```

(Permission rows and the `Publisher Member` group are synced by the existing `post_migrate` handlers; no migration is needed.)

- [ ] **Step 2: Write the failing API tests**

`apps/usage_tracking/tests/test_portal_downloads.py`:

```python
from datetime import UTC, date, datetime

from model_bakery import baker

from apps.content.models import Asset
from apps.core.permissions import PermissionChoice
from apps.core.tests.base import BaseTestCase
from apps.publishers.models import Publisher
from apps.usage_tracking.models import AssetDownloadDaily, AssetDownloadHourly, UsageSyncState
from apps.users.models import User

BASE = "/portal/usage/downloads"
RANGE = "start_date=2026-10-12&end_date=2026-10-13"


def _daily(asset: Asset, day: date, **overrides) -> AssetDownloadDaily:
    values = {
        "day": day,
        "asset_id": asset.id,
        "file_kind": "surah",
        "surah": 1,
        "asset_version_id": None,
        "country": "SA",
        "status_class": "full",
        "requests": 10,
        "bytes": 1000,
        "plays": 4,
    }
    values.update(overrides)
    return AssetDownloadDaily.objects.create(**values)


class TestPortalDownloads(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="usage-staff@example.com", name="Staff", is_staff=True)
        self.publisher = baker.make(Publisher, name="Pub A")
        self.other_publisher = baker.make(Publisher, name="Pub B")
        self.asset = baker.make(Asset, publisher=self.publisher, name="Asset A")
        self.other_asset = baker.make(Asset, publisher=self.other_publisher, name="Asset B")
        UsageSyncState.objects.create(key="cf_asset_downloads", watermark=datetime(2026, 10, 13, 12, tzinfo=UTC))

    def _get(self, path: str):
        return self.client.get(f"{BASE}/{path}", HTTP_X_TENANT=str(self.publisher.id))

    def _allow(self) -> None:
        self.authenticate_user(self.user)
        self.give_permission(self.user, PermissionChoice.PORTAL_READ_USAGE)

    def test_summary_where_permitted_should_total_own_assets_only(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 12))
        _daily(self.asset, date(2026, 10, 13), file_kind="ayah", status_class="partial", requests=5, plays=1)
        _daily(self.other_asset, date(2026, 10, 13), requests=999)

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        assert body["data_until"].startswith("2026-10-13T12:00:00")
        assert body["total"] == {
            "requests_full": 10,
            "requests_partial": 5,
            "requests_other": 0,
            "bytes": 2000,
            "plays": 5,
        }
        assert body["by_file_kind"]["version"]["plays"] == 0
        assert body["by_file_kind"]["ayah"]["requests_partial"] == 5

    def test_summary_where_missing_permission_should_return_403(self):
        # Arrange
        no_perm = User.objects.create_user(email="no-perm@example.com", name="NoPerm", is_staff=False)
        self.authenticate_user(no_perm)

        # Act
        response = self._get(f"summary/?{RANGE}")

        # Assert
        self.assertEqual(403, response.status_code, response.content)
        self.assertEqual("permission_denied", response.json()["error_name"])

    def test_summary_where_asset_of_other_publisher_should_return_404(self):
        # Arrange
        self._allow()

        # Act
        response = self._get(f"summary/?{RANGE}&asset_id={self.other_asset.id}")

        # Assert
        self.assertEqual(404, response.status_code, response.content)
        self.assertEqual("asset_not_found", response.json()["error_name"])

    def test_summary_where_member_of_no_publisher_should_return_zeros(self):
        # Arrange
        outsider = User.objects.create_user(email="outsider@example.com", name="Out", is_staff=False)
        self.authenticate_user(outsider)
        self.give_permission(outsider, PermissionChoice.PORTAL_READ_USAGE)
        _daily(self.asset, date(2026, 10, 13))

        # Act
        response = self.client.get(f"{BASE}/summary/?{RANGE}")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        assert response.json()["total"]["requests_full"] == 0

    def test_summary_where_end_before_start_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("summary/?start_date=2026-10-13&end_date=2026-10-12")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("invalid_range", response.json()["error_name"])

    def test_timeseries_where_daily_should_zero_fill_every_day(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13))

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=day")

        # Assert
        self.assertEqual(200, response.status_code, response.content)
        (series,) = response.json()["series"]
        assert series["key"] == "all"
        assert [p["t"] for p in series["points"]] == ["2026-10-12", "2026-10-13"]
        assert [p["requests_full"] for p in series["points"]] == [0, 10]

    def test_timeseries_where_split_by_file_kind_should_return_series_per_kind(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13), file_kind="ayah")

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=day&split_by=file_kind")

        # Assert
        series = {s["key"]: s for s in response.json()["series"]}
        assert set(series) == {"surah", "ayah", "version"}
        assert series["ayah"]["points"][1]["plays"] == 4
        assert series["surah"]["points"][1]["plays"] == 0

    def test_timeseries_where_hourly_should_read_hourly_table_and_fill_48_points(self):
        # Arrange
        self._allow()
        AssetDownloadHourly.objects.create(
            hour=datetime(2026, 10, 13, 10, tzinfo=UTC),
            asset_id=self.asset.id,
            file_kind="surah",
            surah=1,
            country="SA",
            status_class="full",
            requests=3,
            bytes=30,
            plays=2,
        )

        # Act
        response = self._get(f"timeseries/?{RANGE}&granularity=hour")

        # Assert
        points = response.json()["series"][0]["points"]
        assert len(points) == 48
        assert points[34]["t"].startswith("2026-10-13T10:00:00")
        assert points[34]["plays"] == 2

    def test_timeseries_where_month_range_crosses_year_should_order_months(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2027, 1, 5))

        # Act
        response = self._get("timeseries/?start_date=2026-12-20&end_date=2027-01-10&granularity=month")

        # Assert
        points = response.json()["series"][0]["points"]
        assert [p["t"] for p in points] == ["2026-12-01", "2027-01-01"]
        assert points[1]["requests_full"] == 10

    def test_timeseries_where_hourly_range_over_31_days_should_return_400(self):
        # Arrange
        self._allow()

        # Act
        response = self._get("timeseries/?start_date=2026-09-01&end_date=2026-10-13&granularity=hour")

        # Assert
        self.assertEqual(400, response.status_code, response.content)
        self.assertEqual("range_too_large", response.json()["error_name"])

    def test_breakdown_where_by_asset_should_rank_by_plays_with_labels(self):
        # Arrange
        self._allow()
        second = baker.make(Asset, publisher=self.publisher, name="Asset A2")
        _daily(self.asset, date(2026, 10, 13), plays=1)
        _daily(second, date(2026, 10, 13), plays=9)

        # Act
        response = self._get(f"breakdown/?{RANGE}&by=asset")

        # Assert
        items = response.json()["items"]
        assert [(i["key"], i["label"], i["plays"]) for i in items] == [
            (str(second.id), "Asset A2", 9),
            (str(self.asset.id), "Asset A", 1),
        ]

    def test_breakdown_where_by_surah_should_exclude_version_files(self):
        # Arrange
        self._allow()
        _daily(self.asset, date(2026, 10, 13), surah=2)
        _daily(self.asset, date(2026, 10, 13), file_kind="version", surah=None, asset_version_id=7)

        # Act
        response = self._get(f"breakdown/?{RANGE}&by=surah")

        # Assert
        assert [i["key"] for i in response.json()["items"]] == ["2"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest apps/usage_tracking/tests/test_portal_downloads.py -q`
Expected: FAIL — 404s (routes do not exist).

- [ ] **Step 4: Implement the endpoints**

`apps/usage_tracking/api/portal/downloads.py`:

```python
"""Portal endpoints: asset download statistics for the publisher in the request.

Portal reads query the models directly (repo rule). All buckets are UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from django.db.models import Expression, F, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils.translation import gettext_lazy as _
from ninja import Field, Query, Schema
from pydantic import AwareDatetime

from apps.content.models import Asset
from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.permission_required import permission_required
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.core.permission_utils import permission_class
from apps.core.permissions import PermissionChoice
from apps.usage_tracking.models import (
    AssetDownloadDaily,
    AssetDownloadFileKind,
    AssetDownloadHourly,
    AssetDownloadStatusClass,
    UsageSyncState,
)
from apps.usage_tracking.repositories.asset_downloads import SYNC_KEY

router = ItqanRouter(tags=[NinjaTag.USAGE])

_MAX_HOURLY_DAYS = 31

# Annotation names avoid clashing with the model's own `requests` / `bytes` / `plays` fields.
_METRIC_ANNOTATIONS: dict[str, Any] = {
    "m_full": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.FULL)), 0),
    "m_partial": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.PARTIAL)), 0),
    "m_other": Coalesce(Sum("requests", filter=Q(status_class=AssetDownloadStatusClass.OTHER)), 0),
    "m_bytes": Coalesce(Sum("bytes"), 0),
    "m_plays": Coalesce(Sum("plays"), 0),
}

_ERRORS = {
    400: NinjaErrorResponse[Literal["invalid_range"]] | NinjaErrorResponse[Literal["range_too_large"]],
    403: NinjaErrorResponse[Literal["permission_denied"]],
    404: NinjaErrorResponse[Literal["asset_not_found"]],
}


class MetricsOut(Schema):
    requests_full: int
    requests_partial: int
    requests_other: int
    bytes: int
    plays: int


class SummaryOut(Schema):
    data_until: AwareDatetime | None
    total: MetricsOut
    by_file_kind: dict[str, MetricsOut]


class PointOut(MetricsOut):
    t: str


class SeriesOut(Schema):
    key: str
    points: list[PointOut]


class TimeseriesOut(Schema):
    data_until: AwareDatetime | None
    granularity: str
    series: list[SeriesOut]


class BreakdownItemOut(MetricsOut):
    key: str
    label: str | None


class BreakdownOut(Schema):
    data_until: AwareDatetime | None
    by: str
    items: list[BreakdownItemOut]


class StatsQuery(Schema):
    start_date: date
    end_date: date
    asset_id: int | None = None
    file_kind: AssetDownloadFileKind | None = None


class TimeseriesQuery(StatsQuery):
    granularity: Literal["hour", "day", "month"] = "day"
    split_by: Literal["file_kind", "status_class"] | None = None


class BreakdownQuery(StatsQuery):
    by: Literal["asset", "surah", "country"]
    limit: int = Field(10, ge=1, le=100)


_ZERO = {"m_full": 0, "m_partial": 0, "m_other": 0, "m_bytes": 0, "m_plays": 0}


def _metrics(row: dict[str, Any]) -> dict[str, int]:
    return {
        "requests_full": row["m_full"],
        "requests_partial": row["m_partial"],
        "requests_other": row["m_other"],
        "bytes": row["m_bytes"],
        "plays": row["m_plays"],
    }


def _data_until() -> datetime | None:
    return UsageSyncState.objects.filter(key=SYNC_KEY).values_list("watermark", flat=True).first()


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _scoped(request: Request, params: StatsQuery, model: type[AssetDownloadDaily | AssetDownloadHourly]) -> QuerySet:
    if params.end_date < params.start_date:
        raise ItqanError("invalid_range", _("The end date must not be before the start date."), 400)
    assets = Asset.objects.filter(request.publisher_q())
    if params.asset_id is not None:
        if not assets.filter(id=params.asset_id).exists():
            raise ItqanError("asset_not_found", _("Asset does not exist."), 404)
        queryset = model.objects.filter(asset_id=params.asset_id)
    else:
        queryset = model.objects.filter(asset_id__in=assets.values("id"))
    if params.file_kind:
        queryset = queryset.filter(file_kind=params.file_kind)
    if model is AssetDownloadHourly:
        end = _day_start(params.end_date) + timedelta(days=1)
        return queryset.filter(hour__gte=_day_start(params.start_date), hour__lt=end)
    return queryset.filter(day__gte=params.start_date, day__lte=params.end_date)


def _buckets(params: TimeseriesQuery) -> list[date | datetime]:
    if params.granularity == "hour":
        start = _day_start(params.start_date)
        hours = ((params.end_date - params.start_date).days + 1) * 24
        return [start + timedelta(hours=offset) for offset in range(hours)]
    if params.granularity == "day":
        days = (params.end_date - params.start_date).days + 1
        return [params.start_date + timedelta(days=offset) for offset in range(days)]
    months: list[date | datetime] = []
    current = params.start_date.replace(day=1)
    while current <= params.end_date:
        months.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return months


@router.get(
    "usage/downloads/summary/",
    response={200: SummaryOut, **_ERRORS},
    description="Download totals for the publisher's assets, per file kind (UTC days, inclusive).",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_summary(request: Request, params: StatsQuery = Query(...)):
    queryset = _scoped(request, params, AssetDownloadDaily)
    per_kind = {row["file_kind"]: row for row in queryset.values("file_kind").annotate(**_METRIC_ANNOTATIONS)}
    return {
        "data_until": _data_until(),
        "total": _metrics(queryset.aggregate(**_METRIC_ANNOTATIONS)),
        "by_file_kind": {kind: _metrics(per_kind.get(kind, _ZERO)) for kind in AssetDownloadFileKind.values},
    }


@router.get(
    "usage/downloads/timeseries/",
    response={200: TimeseriesOut, **_ERRORS},
    description="Zero-filled download series (hour granularity limited to 31 days).",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_timeseries(request: Request, params: TimeseriesQuery = Query(...)):
    bucket: Expression | F
    if params.granularity == "hour":
        if (params.end_date - params.start_date).days + 1 > _MAX_HOURLY_DAYS:
            raise ItqanError(
                "range_too_large",
                _("Hourly statistics are limited to {days} days.").format(days=_MAX_HOURLY_DAYS),
                400,
            )
        queryset = _scoped(request, params, AssetDownloadHourly)
        bucket = F("hour")
    else:
        queryset = _scoped(request, params, AssetDownloadDaily)
        bucket = TruncMonth("day") if params.granularity == "month" else F("day")

    group_by = ["bucket", params.split_by] if params.split_by else ["bucket"]
    rows = queryset.annotate(bucket=bucket).values(*group_by).annotate(**_METRIC_ANNOTATIONS)
    by_key: dict[tuple[str, Any], dict[str, Any]] = {
        (row[params.split_by] if params.split_by else "all", row["bucket"]): row for row in rows
    }
    if params.split_by == "file_kind":
        keys = [params.file_kind] if params.file_kind else list(AssetDownloadFileKind.values)
    elif params.split_by == "status_class":
        keys = list(AssetDownloadStatusClass.values)
    else:
        keys = ["all"]
    buckets = _buckets(params)
    return {
        "data_until": _data_until(),
        "granularity": params.granularity,
        "series": [
            {
                "key": key,
                "points": [
                    {"t": moment.isoformat(), **_metrics(by_key.get((key, moment), _ZERO))} for moment in buckets
                ],
            }
            for key in keys
        ],
    }


@router.get(
    "usage/downloads/breakdown/",
    response={200: BreakdownOut, **_ERRORS},
    description="Top assets, surahs or countries by plays.",
)
@permission_required([permission_class(PermissionChoice.PORTAL_READ_USAGE)])
def downloads_breakdown(request: Request, params: BreakdownQuery = Query(...)):
    field = {"asset": "asset_id", "surah": "surah", "country": "country"}[params.by]
    queryset = _scoped(request, params, AssetDownloadDaily)
    if params.by == "surah":
        queryset = queryset.filter(surah__isnull=False)
    rows = list(
        queryset.values(field).annotate(**_METRIC_ANNOTATIONS).order_by("-m_plays", "-m_full", field)[: params.limit]
    )
    labels: dict[Any, str] = {}
    if params.by == "asset":
        labels = dict(Asset.objects.filter(id__in=[row[field] for row in rows]).values_list("id", "name"))
    return {
        "data_until": _data_until(),
        "by": params.by,
        "items": [{"key": str(row[field]), "label": labels.get(row[field]), **_metrics(row)} for row in rows],
    }
```

Notes for the implementer:
- `by_key` lookups compare DB values to generated buckets: hourly values come back as UTC-aware datetimes (equal to the generated UTC datetimes); `TruncMonth("day")` on a `DateField` returns a `date`.
- If `Query(...)` with a plain `Schema` does not bind query params in this ninja version, switch the three query classes to subclass `ninja.FilterSchema` (used the same way in `apps/content/api/portal/access_requests.py`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest apps/usage_tracking/tests/test_portal_downloads.py -q`
Expected: 12 passed.

- [ ] **Step 6: Run the permission-dependent suites**

Run: `uv run pytest apps/publishers apps/usage_tracking -q`
Expected: all pass (group seeding now includes `portal_read_usage`).

---

### Task 7: Localization and docs

**Files:**
- Modify: `locale/ar/LC_MESSAGES/django.po`
- Modify: `docs/ARCHITECTURE.md`, `README.md`
- Modify: `docs/superpowers/specs/2026-10-13-asset-download-stats-design.md` (record the deviations below)

- [ ] **Step 1: Extract strings**

Run: `uv run manage.py extendedmakemessages --no-location --no-wrap --locale=ar --no-fuzzy-matching --keep-header`
Expected: new `msgid`s for `Portal - View Usage Statistics`, `The end date must not be before the start date.`, `Hourly statistics are limited to {days} days.` (`Asset does not exist.` already exists).

- [ ] **Step 2: Add Arabic translations**

In `locale/ar/LC_MESSAGES/django.po` fill:

```
msgid "Portal - View Usage Statistics"
msgstr "البوابة - عرض إحصائيات الاستخدام"

msgid "The end date must not be before the start date."
msgstr "يجب ألا يكون تاريخ النهاية قبل تاريخ البداية."

msgid "Hourly statistics are limited to {days} days."
msgstr "الإحصائيات بالساعة محدودة بـ {days} يومًا."
```

Remove any `#, fuzzy` flag added on these entries.

- [ ] **Step 3: Verify the catalog**

Run: `msgfmt --check --statistics locale/ar/LC_MESSAGES/django.po -o /dev/null && uv run manage.py compilemessages -l ar`
Expected: `N translated messages.` with no "untranslated"/"fuzzy" counts; compile succeeds.

- [ ] **Step 4: Update docs**

`docs/ARCHITECTURE.md` — add a section "Asset download statistics" containing: the four models with one line each, the data source (Cloudflare `httpRequestsAdaptive` + `httpRequestsAdaptiveGroups` on `CF_R2_CUSTOM_DOMAIN`), the hourly sync flow (lock → plan hours from watermark → replace hour atomically → advance watermark), the play definition, and the three portal endpoints with `PORTAL_READ_USAGE`.

`README.md` — in the environment/configuration section, list the seven `ASSET_DOWNLOAD_*` / `ENABLE_ASSET_DOWNLOAD_SYNC` settings with defaults and note that `CF_R2_CUSTOM_DOMAIN` must be set for the sync to run.

Spec — update to match what was built:
- `apps.usage_tracking` is now always installed (previously only with `MIXPANEL_ENABLED`).
- One path filter (`/media/uploads/assets/%`) instead of one per file kind; the parser drops non-download files.
- Query parameters are `start_date` / `end_date` (UTC dates, inclusive), not `from` / `to`.
- The permission is seeded by `post_migrate`, not by a migration.

- [ ] **Step 5: Full verification**

Run:

```bash
uv run pytest apps/usage_tracking apps/publishers apps/content -q
uv run ruff check apps/usage_tracking config apps/core/permissions.py apps/publishers/services/publisher_member_service.py
uv run ruff format --check apps/usage_tracking config
uv run python manage.py makemigrations --check --dry-run
```

Expected: tests pass; ruff clean; `No changes detected`.

- [ ] **Step 6: Hand off**

Report to the user: files changed, test counts, localization result line, and that nothing is committed. Remind them: set `CF_R2_CUSTOM_DOMAIN` on staging before enabling `ENABLE_ASSET_DOWNLOAD_SYNC`.
