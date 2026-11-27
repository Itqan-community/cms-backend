"""Short-lived caching and ETags for the public API's list endpoints.

Lists change rarely and are read often, so browsers and Cloudflare may keep them for 60 seconds
(an edit in the portal shows up within a minute), and a client that sends back the ETag gets an
empty 304 once that minute is over and nothing changed.

It sits outside AppTaggingMiddleware: that middleware tags storage URLs per app and adds
`X-Itqan-App`, so the ETag here hashes the body the client really gets, and an API-key response
stays private so no shared cache hands one app's tagged links to another.
"""

from __future__ import annotations

from collections.abc import Callable
import re

from django.http import HttpRequest, HttpResponse
from django.utils.cache import get_conditional_response, set_response_etag

from apps.usage_tracking.middlewares.app_tagging import APP_HEADER

PUBLIC_LIST_MAX_AGE = 60

# Anonymous-safe lists: the same body for every anonymous caller. Personalized
# recommendations are per user, so they are left out.
_PUBLIC_LIST_PATHS = re.compile(
    r"^/(?:recitations|reciters|riwayahs|packages|recommendations/(?:trending|editorial|similar/\d+))/$"
)


def is_public_list_path(path: str) -> bool:
    return bool(_PUBLIC_LIST_PATHS.match(path))


class PublicListCacheMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if (
            request.method not in ("GET", "HEAD")
            or response.status_code != 200
            or response.streaming
            or not is_public_list_path(request.path)
        ):
            return response
        # Signed-in callers can get per-user fields (e.g. `access` on /packages/).
        user = getattr(request, "user", None)
        personal = response.has_header(APP_HEADER) or bool(user and user.is_authenticated)
        scope = "private" if personal else "public"
        response["Cache-Control"] = f"{scope}, max-age={PUBLIC_LIST_MAX_AGE}"
        set_response_etag(response)
        return get_conditional_response(request, etag=response["ETag"], response=response)
