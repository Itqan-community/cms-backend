"""Public app slugs used to attribute traffic to the API key that produced it."""

from collections.abc import Iterable
import re
import secrets

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils.text import slugify
from django.utils.translation import gettext as _

from apps.core.ninja_utils.errors import ItqanError
from apps.usage_tracking.models import UsageApp

_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38})[a-z0-9]$")
_BASE_MAX = 34  # leaves room for "-xxxx"
# Public-API requests with a warm response cache make no DB queries; keep the slug lookup cached too.
_SLUG_CACHE_TTL = 24 * 3600
_CREATE_ATTEMPTS = 5


def _slug_cache_key(api_key_id: str) -> str:
    return f"usage_app_slug:{api_key_id}"


def unique_slug(name: str) -> str:
    base = slugify(name).replace("_", "-")[:_BASE_MAX].strip("-") or "app"
    if len(base) < 3:
        base = f"app-{base}" if base != "app" else base
    candidate = base
    while UsageApp.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{secrets.token_hex(2)}"
    return candidate


def app_for_key(api_key) -> UsageApp:
    for _attempt in range(_CREATE_ATTEMPTS):
        app = UsageApp.objects.filter(api_key=api_key).first()
        if app is not None:
            return app
        try:
            # A concurrent request can take the slug (or create this key's app) between the check
            # and the insert; the savepoint keeps the caller's transaction usable for the retry.
            with transaction.atomic():
                return UsageApp.objects.create(
                    api_key=api_key, user_id=api_key.user_id, name=api_key.name, slug=unique_slug(api_key.name)
                )
        except IntegrityError:
            continue
    raise RuntimeError(f"could not create a usage app for API key {api_key.pk}")


def slug_for_key(api_key) -> str:
    key = _slug_cache_key(api_key.id)
    slug = cache.get(key)
    if slug is None:
        slug = app_for_key(api_key).slug
        cache.set(key, slug, _SLUG_CACHE_TTL)
    return slug


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
    cache.delete(_slug_cache_key(api_key.id))
    return app


def slug_ids(slugs: Iterable[str]) -> dict[str, int]:
    return dict(UsageApp.objects.filter(slug__in=set(slugs)).values_list("slug", "id"))
