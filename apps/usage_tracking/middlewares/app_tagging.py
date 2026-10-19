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

from apps.usage_tracking.services.usage_apps import slug_for_key
from apps.users.models import APIKey

APP_HEADER = "X-Itqan-App"


def tag_storage_urls(body: bytes, base_url: str, slug: str) -> bytes:
    """Append `?c=slug` to every `<base_url>/media/...` URL in a JSON body that has no query yet."""
    pattern = re.compile(re.escape(base_url.rstrip("/").encode()) + rb'/media/[^"?\\\s]+(?=")')
    return pattern.sub(lambda match: match.group(0) + b"?c=" + slug.encode(), body)


def _private(cache_control: str) -> str:
    if "no-store" in cache_control:
        return "private, no-store"
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
        slug = slug_for_key(api_key)
        response[APP_HEADER] = slug
        # Every tagged response is private, so a shared cache never serves one app's links to another.
        response["Cache-Control"] = _private(response.get("Cache-Control", ""))
        base_url = settings.CLOUDFLARE_R2_PUBLIC_BASE_URL
        if base_url and not response.streaming and response.get("Content-Type", "").startswith("application/json"):
            response.content = tag_storage_urls(response.content, base_url, slug)
        return response
