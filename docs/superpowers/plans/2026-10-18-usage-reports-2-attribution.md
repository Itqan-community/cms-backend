# Usage Reports — Plan 2: Attribution and Django Events (backend)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute traffic to the integrating app (API key), count gallery downloads and CLI
installs that the edge cannot attribute, and fold Django-side usage events into `TrafficEvent`.

**Architecture:** A `UsageApp` row (integer id, public slug) per API key. A middleware tags every
storage URL in API-key-authenticated public-API JSON responses with `?c=<slug>`, sets
`X-Itqan-App: <slug>` and `Cache-Control: private`, so Cloudflare never serves one app's tagged
links to another and Logpush can attribute both the API call (response header) and the later
file requests (`c`). The importer maps slugs to `UsageApp` ids (`app_identified`). Django
records CLI installs at resolve time and an hourly fold-in copies gallery views/presigned
downloads from `content.UsageEvent`, then rebuilds every hour that received Django events.

**Tech Stack:** Django 5, django-ninja, djangorestframework-api-key (`APIKey`, string pk),
Celery beat, Postgres 17.

**Spec:** `docs/superpowers/specs/2026-10-18-usage-reports-design.md` §5.1–5.4, §6, §14 row 2,
§18. Plan 1 (merged first): `docs/superpowers/plans/2026-10-18-usage-reports-1-collection.md`.

## Global Constraints

- All plan-1 constraints apply (backend rules, `uv run --frozen`, BaseTestCase/AAA/naming,
  `patch.object(target, symbol.__name__)`, localized `_()` strings with 0 untranslated,
  docs updated, all settings optional with defaults, raw IPs never stored by the new pipeline).
- Branch `feat/usage-reports-attribution` from `feat/usage-reports` (plan 1, PR #555); rebase
  `--onto origin/staging` once #555 is merged.
- Run pre-commit per file (multi-file runs skip every hook — see memory).
- `TrafficEvent.app_id` and rollup `app_id` refer to `UsageApp.id`.

## Spec amendments made by this plan (apply in Task 7)

1. **`UsageApp`** (usage_tracking) holds the public slug, not `APIKey.public_slug`: `APIKey`'s pk
   is a string, while rollups and monthly uniques key apps by integer. It survives key deletion
   (`SET_NULL`), so history stays attributed.
2. **No Cloudflare API cache rule:** tagged responses are `Cache-Control: private` instead, so
   Cloudflare caches only anonymous responses. Django's Redis response caches stay shared (the
   tag is applied to the cached body on the way out).
3. **API-call attribution** uses an `X-Itqan-App` response header captured by a Logpush custom
   response-header field, not request headers (the edge never sees the API key).
4. **OAuth apps are not tagged** (OAuth is disabled: `ENABLE_OAUTH2=False` everywhere).
5. Parser method rule: files count `GET` only; API routes count `GET` and `POST`
   (`packages/resolve/manifest/` is a POST).
6. Gallery downloads through the custom domain are behind `GALLERY_DOWNLOADS_VIA_CDN`
   (default `False`) until the Cloudflare transform rule exists.
7. Django usage events store the client IP from `X-Forwarded-For` (Caddy forwards
   `CF-Connecting-IP`); before this they stored the proxy address. The fold-in starts at the
   newest `content.UsageEvent` id on its first run (older rows carry proxy IPs).

## Review Focus

1. A JSON body where a storage URL already has a query string, or a non-storage URL → only
   storage `/media/` URLs without a query get `?c=`; nothing else is rewritten.
2. Anonymous public-API responses keep their original `Cache-Control` (edge caching unchanged).
3. A revoked or deleted key's slug in old URLs → `app_unidentified` (deleted) or still attributed
   (revoked, `UsageApp` kept) — never a crash.
4. A Django event and an edge row for the same gallery download → counted once
   (`delivery=cdn` events are not folded in).
5. Fold-in re-run after a crash → no duplicate `TrafficEvent` rows (`ray_id = django:<kind>:<pk>`).

---

### Task 1: `UsageApp` with public slugs, created per API key, shown and editable on API keys

**Files:**
- Modify: `apps/usage_tracking/models.py`, `apps/usage_tracking/apps.py`,
  `apps/users/api/internal/api_keys.py`, `locale/ar/LC_MESSAGES/django.po`
- Create: `apps/usage_tracking/services/usage_apps.py`, `apps/usage_tracking/signals.py`,
  `apps/usage_tracking/migrations/0003_usage_app.py` (generated, then add a `RunPython` backfill)
- Test: `apps/usage_tracking/tests/test_usage_apps.py`, `apps/users/tests/` (extend the existing
  API-keys endpoint test module — find it with `git grep -l "api-keys/" apps/users/tests`)

**Interfaces:**
- Produces: `UsageApp(api_key OneToOne→users.APIKey SET_NULL, user FK→users.User SET_NULL, name,
  slug unique)`; `unique_slug(name: str) -> str`; `app_for_key(api_key) -> UsageApp`
  (get-or-create); `set_app_slug(api_key, slug: str) -> UsageApp` raising `ItqanError`
  `invalid_app_slug` / `app_slug_taken` (400); `slug_ids(slugs: Iterable[str]) -> dict[str, int]`.
- API keys: `ApiKeyOutSchema.app_slug: str | None`; PATCH accepts `app_slug`.

- [ ] **Step 1: Failing tests** (`apps/usage_tracking/tests/test_usage_apps.py`)

```python
# apps/usage_tracking/tests/test_usage_apps.py
import pytest

from apps.core.ninja_utils.errors import ItqanError
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import UsageApp
from apps.usage_tracking.services.usage_apps import app_for_key, set_app_slug, slug_ids, unique_slug
from apps.users.models import APIKey, User


class TestUsageApps(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="dev@example.com", name="Dev")

    def _key(self, name: str) -> APIKey:
        api_key, _ = APIKey.objects.create_key(name=name, user=self.user)
        return api_key

    def test_api_key_where_created_should_get_usage_app_with_slug(self):
        # Act
        api_key = self._key("Quran Companion")

        # Assert
        app = UsageApp.objects.get(api_key=api_key)
        assert (app.slug, app.user_id, app.name) == ("quran-companion", self.user.id, "Quran Companion")

    def test_unique_slug_where_taken_or_not_latin_should_fall_back(self):
        # Arrange
        self._key("Quran Companion")

        # Act / Assert
        assert unique_slug("Quran Companion").startswith("quran-companion-")
        assert unique_slug("تطبيق").startswith("app")

    def test_api_key_where_deleted_should_keep_usage_app(self):
        # Arrange
        api_key = self._key("Temp")
        app_id = app_for_key(api_key).id

        # Act
        api_key.delete()

        # Assert
        assert UsageApp.objects.get(id=app_id).api_key_id is None

    def test_set_app_slug_where_invalid_or_taken_should_raise(self):
        # Arrange
        first, second = self._key("One"), self._key("Two")

        # Act / Assert
        with pytest.raises(ItqanError) as invalid:
            set_app_slug(first, "Bad Slug!")
        with pytest.raises(ItqanError) as taken:
            set_app_slug(first, app_for_key(second).slug)
        assert (invalid.value.error_name, taken.value.error_name) == ("invalid_app_slug", "app_slug_taken")

    def test_slug_ids_where_known_and_unknown_should_map_known_only(self):
        # Arrange
        app = app_for_key(self._key("Known"))

        # Act / Assert
        assert slug_ids(["known", "nope"]) == {"known": app.id}
```

(Check `ItqanError`'s attribute name for the error code in `apps/core/ninja_utils/errors.py`
before running; use it in the last assertion if it is not `error_name`.)

- [ ] **Step 2: Run** `uv run --frozen pytest -q apps/usage_tracking/tests/test_usage_apps.py`
  — Expected: FAIL (`ImportError: UsageApp`).

- [ ] **Step 3: Model** (append to `apps/usage_tracking/models.py`)

```python
class UsageApp(BaseModel):
    """An integrating app: one per API key. Kept when the key is deleted so history stays attributed."""

    api_key = models.OneToOneField(
        "users.APIKey", null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_app"
    )
    user = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_apps")
    name = models.CharField(max_length=50)
    # Public, non-secret: appended to audio/file URLs as `?c=<slug>`.
    slug = models.SlugField(max_length=40, unique=True)
```

- [ ] **Step 4: Service**

```python
# apps/usage_tracking/services/usage_apps.py
"""Public app slugs used to attribute traffic to the API key that produced it."""

from collections.abc import Iterable
import re
import secrets

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.core.ninja_utils.errors import ItqanError
from apps.usage_tracking.models import UsageApp

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38})[a-z0-9]$")
_BASE_MAX = 34  # leaves room for "-xxxx"


def unique_slug(name: str) -> str:
    base = slugify(name)[:_BASE_MAX].strip("-") or "app"
    if len(base) < 3:
        base = f"app-{base}" if base != "app" else base
    candidate = base
    while UsageApp.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


def app_for_key(api_key) -> UsageApp:
    app = UsageApp.objects.filter(api_key=api_key).first()
    if app is not None:
        return app
    return UsageApp.objects.create(api_key=api_key, user_id=api_key.user_id, name=api_key.name, slug=unique_slug(api_key.name))


def set_app_slug(api_key, slug: str) -> UsageApp:
    slug = slug.strip().lower()
    if not _SLUG_RE.match(slug):
        raise ItqanError(
            "invalid_app_slug",
            _("App slug must be 3-40 lowercase letters, digits or hyphens, and start and end with a letter or digit."),
            status_code=400,
        )
    app = app_for_key(api_key)
    if UsageApp.objects.filter(slug=slug).exclude(id=app.id).exists():
        raise ItqanError("app_slug_taken", _("This app slug is already taken."), status_code=400)
    app.slug = slug
    try:
        with transaction.atomic():
            app.save(update_fields=["slug", "updated_at"])
    except IntegrityError as exc:  # lost a race for the same slug
        raise ItqanError("app_slug_taken", _("This app slug is already taken."), status_code=400) from exc
    return app


def slug_ids(slugs: Iterable[str]) -> dict[str, int]:
    return dict(UsageApp.objects.filter(slug__in=set(slugs)).values_list("slug", "id"))
```

- [ ] **Step 5: Signal** (`apps/usage_tracking/signals.py`) and registration in
  `UsageTrackingConfig.ready()` (`from apps.usage_tracking import signals  # noqa: F401`):

```python
# apps/usage_tracking/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey


@receiver(post_save, sender=APIKey, dispatch_uid="usage_tracking_usage_app_for_key")
def create_usage_app(sender, instance: APIKey, created: bool, raw: bool = False, **kwargs) -> None:
    if created and not raw:
        app_for_key(instance)
```

- [ ] **Step 6: Migration** — `uv run --frozen manage.py makemigrations usage_tracking --name usage_app`,
  then add to the generated file (dependencies already include `users`):

```python
def backfill_usage_apps(apps, schema_editor):
    from django.utils.text import slugify

    APIKey = apps.get_model("users", "APIKey")
    UsageApp = apps.get_model("usage_tracking", "UsageApp")
    taken = set(UsageApp.objects.values_list("slug", flat=True))
    for api_key in APIKey.objects.filter(usage_app__isnull=True).iterator():
        base = slugify(api_key.name)[:34].strip("-") or "app"
        slug, n = base, 1
        while slug in taken or len(slug) < 3:
            n += 1
            slug = f"{base}-{n}"
        taken.add(slug)
        UsageApp.objects.create(api_key=api_key, user_id=api_key.user_id, name=api_key.name, slug=slug)
```

and `migrations.RunPython(backfill_usage_apps, migrations.RunPython.noop)` as the last operation.

- [ ] **Step 7: API keys endpoints** — in `apps/users/api/internal/api_keys.py`:
  - `ApiKeyOutSchema`: add `app_slug: str | None = None` and

```python
    @staticmethod
    def resolve_app_slug(obj) -> str | None:
        from apps.usage_tracking.models import UsageApp

        return UsageApp.objects.filter(api_key_id=obj.id).values_list("slug", flat=True).first()
```

  - `ApiKeyPatchInSchema`: add `app_slug: str | None = None`.
  - `create_api_key`: pass `app_slug=app_for_key(api_key).slug` to `ApiKeyCreatedOutSchema`.
  - `update_api_key`: `slug = fields.pop("app_slug", None)`; after `_service.update(...)` (or
    `_service.get(...)` when `fields` is empty), call `set_app_slug(api_key, slug)` when `slug`
    is not `None`; add `NinjaErrorResponse[Literal["invalid_app_slug"]] |
    NinjaErrorResponse[Literal["app_slug_taken"]]` to the 400 union.
  - Endpoint tests (in the existing API-keys test module): list returns `app_slug`; PATCH with
    `{"app_slug": "my-app"}` returns 200 and the new slug; PATCH with `"Bad!"` returns 400
    `invalid_app_slug`.

- [ ] **Step 8: Localize** — run `uv run --frozen manage.py extendedmakemessages --no-location
  --no-wrap --locale=ar --no-fuzzy-matching --keep-header`; Arabic msgstr:
  - "App slug must be 3-40 lowercase letters, digits or hyphens, and start and end with a letter or digit." →
    "يجب أن يتكون المعرّف العام للتطبيق من 3 إلى 40 حرفًا لاتينيًا صغيرًا أو رقمًا أو شرطة، وأن يبدأ وينتهي بحرف أو رقم."
  - "This app slug is already taken." → "هذا المعرّف العام للتطبيق مستخدم بالفعل."
  Confirm `msgfmt --check --statistics` shows 0 untranslated.

- [ ] **Step 9: Run** `uv run --frozen pytest -q apps/usage_tracking/tests/test_usage_apps.py apps/users`
  — Expected: all passed.

---

### Task 2: App-tagging middleware for the public API

**Files:**
- Create: `apps/usage_tracking/middlewares/app_tagging.py`
- Modify: `config/settings/base.py` (MIDDLEWARE: add
  `"apps.usage_tracking.middlewares.app_tagging.AppTaggingMiddleware"` directly after
  `django.middleware.common.CommonMiddleware`), `config/developers_api.py` (docs paragraph)
- Test: `apps/usage_tracking/tests/test_app_tagging.py`

**Interfaces:**
- Consumes: Task 1 `app_for_key`; `settings.CLOUDFLARE_R2_PUBLIC_BASE_URL`; Ninja sets
  `request.auth` to the `APIKey` for API-key auth (`apps/core/ninja_utils/auth.py:ApiKeyAuth`).
- Produces: `tag_storage_urls(body: bytes, base_url: str, slug: str) -> bytes`;
  `AppTaggingMiddleware`; response header `X-Itqan-App`.

- [ ] **Step 1: Failing tests**

```python
# apps/usage_tracking/tests/test_app_tagging.py
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, override_settings

from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.middlewares.app_tagging import AppTaggingMiddleware, tag_storage_urls
from apps.users.models import APIKey, User

BASE = "https://storage.example.com"


class TestTagStorageUrls:
    def test_tag_storage_urls_where_storage_media_url_should_append_slug(self):
        # Arrange
        body = b'{"audio_url":"https://storage.example.com/media/uploads/assets/1/recitations/001.mp3"}'

        # Act
        result = tag_storage_urls(body, BASE, "my-app")

        # Assert
        assert result == b'{"audio_url":"https://storage.example.com/media/uploads/assets/1/recitations/001.mp3?c=my-app"}'

    def test_tag_storage_urls_where_query_present_or_other_host_should_leave_alone(self):
        # Arrange
        body = (
            b'{"a":"https://storage.example.com/media/x.mp3?v=2",'
            b'"b":"https://other.example.com/media/x.mp3","c":"https://storage.example.com/static/x.css"}'
        )

        # Act / Assert
        assert tag_storage_urls(body, BASE, "my-app") == body


@override_settings(CLOUDFLARE_R2_PUBLIC_BASE_URL=BASE)
class TestAppTaggingMiddleware(BaseTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.create_user(email="dev2@example.com", name="Dev")
        self.api_key, _ = APIKey.objects.create_key(name="My App", user=user)

    def _run(self, response: HttpResponse, auth=None) -> HttpResponse:
        request = RequestFactory().get("/recitations/1/")

        def view(req):
            req.auth = auth
            return response

        return AppTaggingMiddleware(view)(request)

    def test_middleware_where_api_key_auth_should_tag_body_set_header_and_private(self):
        # Arrange
        response = JsonResponse({"audio_url": f"{BASE}/media/a.mp3"})
        response["Cache-Control"] = "public, max-age=300, s-maxage=300"

        # Act
        result = self._run(response, auth=self.api_key)

        # Assert
        assert b"a.mp3?c=my-app" in result.content
        assert result["X-Itqan-App"] == "my-app"
        assert result["Cache-Control"] == "private, max-age=300"

    def test_middleware_where_anonymous_should_change_nothing(self):
        # Arrange
        response = JsonResponse({"audio_url": f"{BASE}/media/a.mp3"})
        response["Cache-Control"] = "public, max-age=300, s-maxage=300"

        # Act
        result = self._run(response, auth=None)

        # Assert
        assert b"?c=" not in result.content
        assert "X-Itqan-App" not in result
        assert result["Cache-Control"] == "public, max-age=300, s-maxage=300"
```

- [ ] **Step 2: Run** — Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/middlewares/app_tagging.py
"""Attributes public-API traffic to the calling app (API key).

For API-key-authenticated JSON responses: storage file URLs get `?c=<app slug>` (so later
plays/downloads are attributable at the edge), `X-Itqan-App` names the app for the Logpush row of
this call, and caching becomes private so Cloudflare never serves one app's tagged links to another.
Anonymous responses are untouched. The tag is applied on the way out, so Django's shared
Redis response caches stay untagged.
"""

from __future__ import annotations

from collections.abc import Callable
import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey

APP_HEADER = "X-Itqan-App"


def tag_storage_urls(body: bytes, base_url: str, slug: str) -> bytes:
    """Append `?c=slug` to every `<base_url>/media/...` URL in a JSON body that has no query yet."""
    pattern = re.compile(re.escape(base_url.rstrip("/").encode()) + rb'/media/[^"?\\\s]+(?=")')
    return pattern.sub(lambda match: match.group(0) + b"?c=" + slug.encode(), body)


def _private(cache_control: str) -> str:
    max_age = re.search(r"(?<!s-)max-age=(\d+)", cache_control)
    return f"private, max-age={max_age.group(1)}" if max_age else "private, no-cache"


class AppTaggingMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        api_key = getattr(request, "auth", None)
        if not isinstance(api_key, APIKey):
            return response
        slug = app_for_key(api_key).slug
        response[APP_HEADER] = slug
        if response.has_header("Cache-Control"):
            response["Cache-Control"] = _private(response["Cache-Control"])
        base_url = settings.CLOUDFLARE_R2_PUBLIC_BASE_URL
        if (
            base_url
            and not response.streaming
            and response.get("Content-Type", "").startswith("application/json")
        ):
            response.content = tag_storage_urls(response.content, base_url, slug)
        return response
```

- [ ] **Step 4: Developer docs** — in `config/developers_api.py` `_DEVELOPERS_API_DESCRIPTION`,
  after the "Send the key in the `X-API-Key` header on each request." line add:

```
Responses to requests with an API key carry an `X-Itqan-App` header with your app's public \
slug, and audio and file URLs get a `c=<slug>` query parameter. Keep that parameter when you \
play or download the files: it is how publishers see that their content is used in your app. \
You can change the slug on the **API Keys** page.
```

- [ ] **Step 5: Run** the new tests plus a public-API smoke test:
  `uv run --frozen pytest -q apps/usage_tracking/tests/test_app_tagging.py apps/content/tests apps/package_manager/tests`
  — Expected: all passed (existing public-API tests use no API key, or assert fields that the
  tag does not change; if one asserts an exact URL for an API-key request, update it to expect
  `?c=<slug>` and note it in the ledger).

---

### Task 3: Importer attribution (`app_identified`) and the method rule

**Files:**
- Modify: `apps/usage_tracking/services/logpush_parser.py`, `apps/usage_tracking/services/traffic_classify.py`,
  `apps/usage_tracking/services/logpush_import.py`
- Test: extend `test_logpush_parser.py`, `test_traffic_classify.py`, `test_logpush_import.py`

**Interfaces:**
- Consumes: Task 1 `slug_ids`; Task 2 header name `x-itqan-app` (Logpush custom response field,
  output under `ResponseHeaders`).
- Produces: `channel_for(kind, family, *, has_install_id, app_identified=False)`; parser reads
  `ResponseHeaders["x-itqan-app"]` into `app_slug_raw` when there is no `c` parameter.

- [ ] **Step 1: Failing tests**

```python
# append to apps/usage_tracking/tests/test_logpush_parser.py
class TestAttributionParsing:
    def test_parse_line_where_api_response_names_app_should_use_it(self):
        # Act
        parsed = parse_line(_line(ClientRequestURI="/recitations/13/", ResponseHeaders={"x-itqan-app": "my-app"}))

        # Assert
        assert parsed.app_slug_raw == "my-app"

    def test_parse_line_where_api_post_should_keep_but_file_post_should_skip(self):
        # Act / Assert
        assert parse_line(_line(ClientRequestURI="/packages/resolve/manifest/", ClientRequestMethod="POST")) is not None
        assert parse_line(_line(ClientRequestMethod="POST")) is None
```

```python
# append to apps/usage_tracking/tests/test_traffic_classify.py
class TestIdentifiedChannel:
    def test_channel_for_where_app_identified_should_beat_family_but_not_gallery_or_cli(self):
        # Act / Assert
        assert channel_for(TrafficKind.AUDIO_SURAH, "dalvik", has_install_id=False, app_identified=True) == TrafficChannel.APP_IDENTIFIED
        assert channel_for(TrafficKind.GALLERY_DOWNLOAD, "browser", has_install_id=False, app_identified=True) == TrafficChannel.GALLERY
        assert channel_for(TrafficKind.VERSION_FILE, "itqan-cli", has_install_id=False, app_identified=True) == TrafficChannel.CLI
```

```python
# append to TestBuildEvents in apps/usage_tracking/tests/test_logpush_import.py
    def test_build_events_where_slug_known_should_attribute_app(self):
        # Arrange
        from apps.usage_tracking.services.usage_apps import app_for_key
        from apps.users.models import APIKey, User

        user = User.objects.create_user(email="dev3@example.com", name="Dev")
        api_key, _ = APIKey.objects.create_key(name="Tagged App", user=user)
        app = app_for_key(api_key)
        uri = f"/media/uploads/assets/13/recitations/091.mp3?c={app.slug}"

        # Act
        [known, unknown] = build_events(
            [parse_line(_line("k1", ClientRequestURI=uri)), parse_line(_line("u1", ClientRequestURI=uri + "x"))]
        )

        # Assert
        assert (known.app_id, known.channel) == (app.id, TrafficChannel.APP_IDENTIFIED)
        assert (unknown.app_id, unknown.channel) == (None, TrafficChannel.APP_UNIDENTIFIED)
```

- [ ] **Step 2: Run** — Expected: the new tests FAIL.

- [ ] **Step 3: Implement**
  - `traffic_classify.channel_for`: add keyword `app_identified: bool = False`; after the CLI rule
    insert `if app_identified: return TrafficChannel.APP_IDENTIFIED`; update the docstring
    (remove "added in plan 2").
  - `logpush_parser.parse_line`: replace the GET-only check with

```python
        method = record.get("ClientRequestMethod") or "GET"
        if method not in ("GET", "POST"):  # OPTIONS preflights and HEAD probes are not usage
            return None
```

    and after `located` is computed: `if method == "POST" and kind != TrafficKind.API_CALL: return None`.
    Set `app_slug_raw=_text(_first(params, "c") or (record.get("ResponseHeaders") or {}).get("x-itqan-app"), 64)`.
  - `logpush_import._Resolver.__init__`: `self._apps = slug_ids(p.app_slug_raw for p in parsed if p.app_slug_raw)`;
    add `def app_id(self, parsed) -> int | None: return self._apps.get(parsed.app_slug_raw)`.
    In `build_events`: `app_id = resolver.app_id(request)`; pass `app_id=app_id` and
    `channel_for(..., app_identified=app_id is not None)`.

- [ ] **Step 4: Run** `uv run --frozen pytest -q apps/usage_tracking` — Expected: all passed.

---

### Task 4: Client IP for Django events, gallery downloads through the CDN

**Files:**
- Create: `apps/core/utils/client_ip.py` (or add `client_ip()` to an existing request-utils
  module if `git grep -n "def .*request" apps/core/utils` shows one)
- Modify: `apps/content/api/internal/assets_download.py`, `apps/content/api/internal/assets_detail.py`,
  `apps/core/ninja_utils/throttle.py` (reuse the helper), `config/settings/base.py`
  (`GALLERY_DOWNLOADS_VIA_CDN = config("GALLERY_DOWNLOADS_VIA_CDN", default=False, cast=bool)`)
- Test: `apps/core/tests/test_client_ip.py`; extend the existing download endpoint tests
  (`git grep -l "assets/{id}/download\|download_asset" apps/content/tests`)

**Interfaces:**
- Produces: `client_ip(request) -> str | None` (first `X-Forwarded-For` entry, else
  `REMOTE_ADDR`); `UsageEvent.metadata["delivery"]` = `"cdn"` or `"presigned"` on downloads.

- [ ] **Step 1: Failing tests**

```python
# apps/core/tests/test_client_ip.py
from django.test import RequestFactory

from apps.core.utils.client_ip import client_ip


class TestClientIp:
    def test_client_ip_where_forwarded_should_take_first_hop(self):
        # Arrange
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.2", REMOTE_ADDR="10.0.0.2")

        # Act / Assert
        assert client_ip(request) == "203.0.113.7"

    def test_client_ip_where_not_forwarded_should_use_remote_addr(self):
        # Act / Assert
        assert client_ip(RequestFactory().get("/", REMOTE_ADDR="10.0.0.2")) == "10.0.0.2"
```

  Download endpoint tests (in the existing module, same setup it uses for an open-access asset):
  - with `GALLERY_DOWNLOADS_VIA_CDN=True` and `CLOUDFLARE_R2_ENDPOINT` set, an open-access asset
    returns `download_url` = `<file url>?download=<url-quoted filename>` and the queued
    `create_usage_event_task` payload has `metadata["delivery"] == "cdn"` and
    `ip_address == "203.0.113.7"` (request sent with `HTTP_X_FORWARDED_FOR`);
  - with the flag off, `download_url` is the presigned URL and `delivery == "presigned"`.
  Patch `create_usage_event_task.delay` with `patch.object(tasks_module, "create_usage_event_task")`
  following how the existing download tests already patch it.

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# apps/core/utils/client_ip.py
from django.http import HttpRequest


def client_ip(request: HttpRequest) -> str | None:
    """The visitor's IP. Caddy sets X-Forwarded-For from Cloudflare's CF-Connecting-IP."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR")
```

  In `assets_download.download_asset`, replace the `if settings.CLOUDFLARE_R2_ENDPOINT:` block with:

```python
    if settings.CLOUDFLARE_R2_ENDPOINT and settings.GALLERY_DOWNLOADS_VIA_CDN and asset.is_open_access:
        # Through the custom domain, so the edge sees (and counts) the download; a Cloudflare
        # transform rule turns `download` into Content-Disposition: attachment.
        download_url = f"{asset_latest_version.file_url.url}?download={quote(filename)}"
        delivery = "cdn"
    elif settings.CLOUDFLARE_R2_ENDPOINT:
        # Object storage (staging/prod): hand out a short-lived pre-signed URL.
        key = f"media/{asset_latest_version.file_url.name}"  # object key within the bucket
        download_url = generate_presigned_download_url(key=key, filename=filename, expires_in=3600)
        delivery = "presigned"
    else:
        # Local/dev without object storage: serve the file via its media URL.
        download_url = request.build_absolute_uri(asset_latest_version.file_url.url)
        delivery = "local"
```

  (`from urllib.parse import quote`), merge `"delivery": delivery` into the event `metadata`, and
  use `client_ip(request)` for `ip_address` here, in `assets_detail.py`'s view event and in
  `throttle.py` (line 54).

- [ ] **Step 4: Run** `uv run --frozen pytest -q apps/core apps/content` — Expected: all passed.

---

### Task 5: CLI install events at resolve time

**Files:**
- Create: `apps/usage_tracking/services/install_events.py`
- Modify: `apps/package_manager/api/public/packages.py` (`resolve_package_manifest`,
  the `packages/resolve/{slug}/` view)
- Test: `apps/usage_tracking/tests/test_install_events.py`; one endpoint test in the existing
  package resolve test module asserting a `cli_install` row after a resolve with
  `HTTP_USER_AGENT="itqan-cli/0.4.0"` and `HTTP_X_ITQAN_INSTALL_ID="u-1"`

**Interfaces:**
- Consumes: plan-1 classifiers/identity; Task 1 `app_for_key`; Task 4 `client_ip`.
- Produces: `record_installs(request, results: Iterable[ResolvedPackage]) -> int` writing
  `TrafficEvent(source=django, kind=cli_install, ray_id="django:install:<uuid4 hex>")`.

- [ ] **Step 1: Failing test**

```python
# apps/usage_tracking/tests/test_install_events.py
from types import SimpleNamespace

from django.test import RequestFactory, override_settings
from model_bakery import baker

from apps.content.models import Asset, AssetVersion, CategoryChoice
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import TrafficChannel, TrafficEvent, TrafficKind, TrafficSource
from apps.usage_tracking.services.install_events import record_installs


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestRecordInstalls(BaseTestCase):
    def test_record_installs_where_cli_resolves_should_store_one_event_per_package(self):
        # Arrange
        asset = baker.make(Asset, category=CategoryChoice.MUSHAF)
        version = baker.make(AssetVersion, asset=asset)
        result = SimpleNamespace(asset=asset, asset_version=version, asset_language=version.asset_language)
        request = RequestFactory().get(
            "/packages/resolve/x/",
            HTTP_USER_AGENT="itqan-cli/0.4.0",
            HTTP_X_ITQAN_INSTALL_ID="u-1",
            HTTP_X_FORWARDED_FOR="203.0.113.7",
            HTTP_CF_IPCOUNTRY="SA",
        )
        request.auth = None

        # Act
        stored = record_installs(request, [result])

        # Assert
        event = TrafficEvent.objects.get()
        assert stored == 1
        assert (event.source, event.kind, event.channel, event.country) == (
            TrafficSource.DJANGO,
            TrafficKind.CLI_INSTALL,
            TrafficChannel.CLI,
            "SA",
        )
        assert (event.asset_id, event.asset_version_id, len(event.install_id)) == (asset.id, version.id, 64)
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/services/install_events.py
"""Records one `cli_install` traffic event per package a client resolves (Django side)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
import uuid

from apps.core.utils.client_ip import client_ip
from apps.usage_tracking.models import TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.services.download_paths import normalize_country
from apps.usage_tracking.services.traffic_classify import channel_for, is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import install_id_for, listener_id_for
from apps.usage_tracking.services.usage_apps import app_for_key
from apps.users.models import APIKey


def record_installs(request, results: Iterable) -> int:
    user_agent = request.headers.get("User-Agent", "")[:1024]
    family = ua_family(user_agent)
    raw_install = request.headers.get("X-Itqan-Install-Id", "")[:64]
    api_key = getattr(request, "auth", None)
    app_id = app_for_key(api_key).id if isinstance(api_key, APIKey) else None
    ip = client_ip(request) or ""
    now = datetime.now(UTC)
    events = []
    for result in results:
        ray_id = f"django:install:{uuid.uuid4().hex}"
        events.append(
            TrafficEvent(
                ray_id=ray_id,
                occurred_at=now,
                source=TrafficSource.DJANGO,
                kind=TrafficKind.CLI_INSTALL,
                asset_id=result.asset.id,
                asset_version_id=result.asset_version.pk,
                language=result.asset_language.language if result.asset_language else "",
                country=normalize_country(request.headers.get("CF-IPCountry")),
                channel=channel_for(
                    TrafficKind.CLI_INSTALL, family, has_install_id=bool(raw_install), app_identified=app_id is not None
                ),
                platform=platform_for(user_agent, family),
                app_id=app_id,
                endpoint=request.path[:128],
                path=request.path[:512],
                status_class=TrafficStatusClass.FULL,
                listener_id=listener_id_for(ip, user_agent, ray_id),
                install_id=install_id_for(raw_install),
                ua_family=family,
                is_bot=is_bot_user_agent(user_agent),
            )
        )
    TrafficEvent.objects.bulk_create(events)
    return len(events)
```

  In `packages.py`, call `record_installs(request, results)` in `resolve_package_manifest` after
  `results` is computed, and `record_installs(request, [result])` in the single-slug resolve view
  after it resolves. Rollups for these rows come from Task 6.

- [ ] **Step 4: Run** `uv run --frozen pytest -q apps/usage_tracking apps/package_manager` — Expected: all passed.

---

### Task 6: Hourly Django fold-in and rollup of Django-sourced events

**Files:**
- Create: `apps/usage_tracking/services/django_foldin.py`
- Modify: `apps/usage_tracking/models.py` (`UsageImportState.cursor = models.BigIntegerField(null=True, blank=True)`
  + generated migration `0004_usage_import_state_cursor`), `apps/usage_tracking/tasks.py`, `config/celery.py`
- Test: `apps/usage_tracking/tests/test_django_foldin.py`

**Interfaces:**
- Consumes: plan-1 repository (`rebuild_hour`, locks/state), classifiers, identity;
  `content.UsageEvent` (`usage_kind` `view`/`file_download`, `metadata["delivery"]`,
  `ip_address`, `user_agent`, `created_at`).
- Produces: `fold_in_django_events(now=None) -> FoldInResult(events: int, hours: int, error: str)`;
  task `fold_in_django_events_task` (beat: minute 15); job key `DJANGO_FOLDIN_JOB = "django_foldin"`
  (add to `_LOCK_IDS` with `7_340_212_030`).

- [ ] **Step 1: Failing tests**

```python
# apps/usage_tracking/tests/test_django_foldin.py
from datetime import UTC, datetime

from django.test import override_settings
from model_bakery import baker

from apps.content.models import Asset, CategoryChoice, UsageEvent
from apps.core.tests.base import BaseTestCase
from apps.usage_tracking.models import TrafficEvent, TrafficHourly, TrafficKind, UsageImportState
from apps.usage_tracking.services.django_foldin import fold_in_django_events
from apps.users.models import User


@override_settings(USAGE_IDENTITY_KEY="identity")
class TestFoldIn(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(email="viewer@example.com", name="Viewer")
        self.asset = baker.make(Asset, category=CategoryChoice.MUSHAF)

    def _event(self, kind: str, delivery: str | None = None) -> UsageEvent:
        metadata = {"delivery": delivery} if delivery else {}
        return UsageEvent.objects.create(
            developer_user=self.user,
            usage_kind=kind,
            asset_id=self.asset.id,
            metadata=metadata,
            ip_address="203.0.113.7",
            user_agent="Mozilla/5.0",
            effective_license=self.asset.license,
        )

    def test_fold_in_where_first_run_should_start_after_existing_events(self):
        # Arrange
        self._event("view")

        # Act
        result = fold_in_django_events()

        # Assert
        assert result.events == 0
        assert not TrafficEvent.objects.exists()

    def test_fold_in_where_new_view_and_presigned_download_should_copy_and_skip_cdn(self):
        # Arrange
        fold_in_django_events()  # sets the cursor
        view, presigned, cdn = self._event("view"), self._event("file_download", "presigned"), self._event("file_download", "cdn")

        # Act
        result = fold_in_django_events()
        fold_in_django_events()  # re-run: no duplicates

        # Assert
        kinds = dict(TrafficEvent.objects.values_list("ray_id", "kind"))
        assert kinds == {f"django:view:{view.pk}": TrafficKind.VIEW, f"django:download:{presigned.pk}": TrafficKind.GALLERY_DOWNLOAD}
        assert f"django:download:{cdn.pk}" not in kinds
        assert result.events == 2
        assert TrafficHourly.objects.exists()
```

- [ ] **Step 2: Run** — Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# apps/usage_tracking/services/django_foldin.py
"""Hourly: copy Django usage events into traffic events and roll up hours with Django rows.

Copies gallery views and downloads served by presigned URLs (CDN downloads are counted from the
edge), and rebuilds every hour that received Django-sourced traffic events since the last run,
including CLI installs written at resolve time. `ray_id = django:<kind>:<pk>` keeps re-runs safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging

from django.conf import settings
from django.db.models import Max

from apps.content.models import UsageEvent
from apps.usage_tracking.models import TrafficEvent, TrafficKind, TrafficSource, TrafficStatusClass
from apps.usage_tracking.repositories.traffic import DJANGO_FOLDIN_JOB, TrafficRepository, floor_hour
from apps.usage_tracking.services.traffic_classify import is_bot_user_agent, platform_for, ua_family
from apps.usage_tracking.services.traffic_identity import listener_id_for
from apps.usage_tracking.models import TrafficChannel

logger = logging.getLogger(__name__)

_BATCH = 5000
_EVENT_KINDS = {
    UsageEvent.UsageKindChoice.VIEW: ("view", TrafficKind.VIEW, TrafficChannel.WEB),
    UsageEvent.UsageKindChoice.FILE_DOWNLOAD: ("download", TrafficKind.GALLERY_DOWNLOAD, TrafficChannel.GALLERY),
}


@dataclass(frozen=True, slots=True)
class FoldInResult:
    events: int
    hours: int
    error: str


def _copy(event: UsageEvent) -> TrafficEvent | None:
    prefix, kind, channel = _EVENT_KINDS[event.usage_kind]
    if kind == TrafficKind.GALLERY_DOWNLOAD and (event.metadata or {}).get("delivery") == "cdn":
        return None  # the edge already counted this download
    ray_id = f"django:{prefix}:{event.pk}"
    user_agent = (event.user_agent or "")[:1024]
    family = ua_family(user_agent)
    return TrafficEvent(
        ray_id=ray_id,
        occurred_at=event.created_at,
        source=TrafficSource.DJANGO,
        kind=kind,
        asset_id=event.asset_id,
        language=str((event.metadata or {}).get("language") or "")[:10],
        country="XX",
        channel=channel,
        platform=platform_for(user_agent, family),
        status_class=TrafficStatusClass.FULL,
        listener_id=listener_id_for(event.ip_address or "", user_agent, ray_id),
        ua_family=family,
        is_bot=is_bot_user_agent(user_agent),
    )


def fold_in_django_events(now: datetime | None = None) -> FoldInResult:
    now = now or datetime.now(UTC)
    repo = TrafficRepository()
    if not repo.try_lock(DJANGO_FOLDIN_JOB):
        return FoldInResult(0, 0, "")
    copied = hours_rebuilt = 0
    error = ""
    try:
        state = repo.get_state(DJANGO_FOLDIN_JOB)
        if state.cursor is None:
            # First run: older UsageEvent rows carry the proxy IP, so start after them.
            start_id = UsageEvent.objects.aggregate(top=Max("id"))["top"] or 0
            last_traffic_id = TrafficEvent.objects.aggregate(top=Max("id"))["top"] or 0
            repo.set_cursor(DJANGO_FOLDIN_JOB, start_id, traffic_cursor=last_traffic_id)
            return FoldInResult(0, 0, "")
        events = list(
            UsageEvent.objects.filter(id__gt=state.cursor, usage_kind__in=list(_EVENT_KINDS)).order_by("id")[:_BATCH]
        )
        rows = [row for row in (_copy(event) for event in events) if row is not None]
        TrafficEvent.objects.bulk_create(rows, ignore_conflicts=True)
        copied = len(rows)
        # Every hour that gained Django-sourced rows since the last run (fold-in and CLI installs).
        new_rows = TrafficEvent.objects.filter(source=TrafficSource.DJANGO, id__gt=state.traffic_cursor or 0)
        hours = {floor_hour(at) for at in new_rows.values_list("occurred_at", flat=True)}
        play_window = timedelta(minutes=settings.ASSET_DOWNLOAD_PLAY_WINDOW_MINUTES)
        for hour in sorted(hours):
            repo.rebuild_hour(hour, play_window)
        hours_rebuilt = len(hours)
        top_traffic = new_rows.aggregate(top=Max("id"))["top"] or state.traffic_cursor or 0
        repo.set_cursor(DJANGO_FOLDIN_JOB, events[-1].id if events else state.cursor, traffic_cursor=top_traffic)
    except Exception as exc:  # noqa: BLE001 — record, alert, and let the next run resume
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("fold_in_django_events: run failed")
    finally:
        try:
            repo.record_run(DJANGO_FOLDIN_JOB, now, error)
        finally:
            repo.unlock(DJANGO_FOLDIN_JOB)
    return FoldInResult(copied, hours_rebuilt, error)
```

  Model + repository support (keep the cursors in `UsageImportState`):
  - `UsageImportState`: add `cursor = models.BigIntegerField(null=True, blank=True)` and
    `traffic_cursor = models.BigIntegerField(null=True, blank=True)`; generate
    `0004_usage_import_state_cursors`.
  - `TrafficRepository`: `DJANGO_FOLDIN_JOB = "django_foldin"` (lock id `7_340_212_030`);
    `get_state(key) -> UsageImportState` (`get_or_create`); `set_cursor(key, cursor, *, traffic_cursor)`
    (`update_or_create` with both fields).
  - Order the steps so a crash between the copy and the rebuild re-copies nothing (ignore_conflicts)
    and rebuilds the same hours next run (the traffic cursor only advances after the rebuild).

  Task + beat (minute 15):

```python
@shared_task(acks_late=True, soft_time_limit=900, time_limit=960, ignore_result=True)
def fold_in_django_events_task() -> None:
    """Copy Django usage events into traffic events and roll up their hours."""
    result = fold_in_django_events()
    logger.info("fold_in_django_events_task: events=%d hours=%d error=%r", result.events, result.hours, result.error)
```

- [ ] **Step 4: Run** `uv run --frozen pytest -q apps/usage_tracking` — Expected: all passed.

---

### Task 7: Settings, CI/CD, docs, spec amendments, Cloudflare steps, verification

- [ ] **Step 1:** env files + `ci-cd.yml` (both blocks):
  `GALLERY_DOWNLOADS_VIA_CDN=${{ vars.<ENV>_GALLERY_DOWNLOADS_VIA_CDN || 'False' }}`.
- [ ] **Step 2:** README: add `GALLERY_DOWNLOADS_VIA_CDN` to the usage-reports table, and a
  short "App attribution" paragraph (slug per API key, `?c=`, `X-Itqan-App`, private caching).
- [ ] **Step 3:** ARCHITECTURE.md: extend "Usage reports: traffic collection" with `UsageApp`, the
  middleware, install events, the fold-in job (minute 15) and the updated channel rule order
  (gallery, cli, app_identified, web, app_unidentified, script, other).
- [ ] **Step 4:** Spec: add "§19 Amendments from plan 2" with the seven amendments above.
- [ ] **Step 5:** Localization check (0 untranslated), pre-commit per file (2 clean passes),
  `makemigrations --check` (only djangosaml2idp), full suite green.
- [ ] **Step 6:** Performance: middleware on a 100-track JSON response (~40 KB) under 2 ms
  (`timeit` of `tag_storage_urls`); resolve endpoint query count unchanged except the single
  `bulk_create` (assert with `django_assert_num_queries` or `CaptureQueriesContext` in one test).

## Cloudflare steps for the user (after this plan merges; report them in the final message)

1. **Custom log fields → Response headers:** add `x-itqan-app`; add the `ResponseHeaders` field to
   both Logpush jobs.
2. **Transform rule** (zone `itqan.dev` → Rules → Transform Rules → *Modify Response Header* →
   *Create rule*), name `gallery-download-attachment`:
   - When: `(http.host in {"storage.cms.itqan.dev" "staging.storage.cms.itqan.dev"} and any(http.request.uri.args.names[*] == "download"))`
   - Then: *Set dynamic* `Content-Disposition` =
     `concat("attachment; filename=\"", http.request.uri.args["download"][0], "\"")`
   Then set `<ENV>_GALLERY_DOWNLOADS_VIA_CDN=True` (staging first).
3. **Cache rule (required):** `api.cms.itqan.dev` and `staging.api.cms.itqan.dev`, when
   `any(http.request.headers.names[*] == "x-api-key")` → *Bypass cache* (spec §19.9).
4. **Optional cache rule** for when storage caching is turned on: storage hosts, cache key query
   string → *Ignore query string* for `c` and `download`.
