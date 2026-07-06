import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from ninja.throttling import AnonRateThrottle as NinjaAnonRateThrottle, UserRateThrottle as NinjaUserRateThrottle
from rest_framework.throttling import UserRateThrottle as DRFUserRateThrottle

logger = logging.getLogger(__name__)


def build_throttle_log_context(
    request: HttpRequest | None, *, scope: str, rate: str | None, key: str | None
) -> dict[str, Any]:
    """
    Collect every piece of client/user data we have about a throttled request,
    for structured logging. Defensive: never raises, since it runs on the
    request-rejection path.
    """
    context: dict[str, Any] = {
        "throttle_scope": scope,
        "throttle_rate": rate,
        "throttle_cache_key": key,
    }
    if request is None:
        return context

    user = getattr(request, "user", None)
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))
    context["is_authenticated"] = is_authenticated
    if is_authenticated:
        context["user_id"] = getattr(user, "pk", None)
        context["user_email"] = getattr(user, "email", None)
        context["user_name"] = getattr(user, "name", None)
        context["is_staff"] = getattr(user, "is_staff", None)

    # OAuth2 application / token (django-oauth-toolkit), when present.
    # OAuth2TokenMiddleware sets request.access_token for OAuth2-authenticated
    # requests.
    access_token = getattr(request, "access_token", None)
    if access_token is not None:
        application = getattr(access_token, "application", None)
        context["oauth2_application_id"] = getattr(application, "pk", None)
        context["oauth2_application_name"] = getattr(application, "name", None)
        context["oauth2_client_id"] = getattr(application, "client_id", None)

    # Request metadata.
    meta = request.META
    context["client_ip"] = meta.get("HTTP_X_FORWARDED_FOR") or meta.get("REMOTE_ADDR")
    context["remote_addr"] = meta.get("REMOTE_ADDR")
    context["path"] = getattr(request, "path", None)
    context["method"] = getattr(request, "method", None)
    context["user_agent"] = meta.get("HTTP_USER_AGENT")
    context["referer"] = meta.get("HTTP_REFERER")
    context["origin"] = meta.get("HTTP_ORIGIN")
    return context


class NinjaUserPathRateThrottle(NinjaUserRateThrottle):
    """
    This Throttle will not throttle any request
    however it will only log and `error` to catch FE duplicate requests
    """

    scope = "user"

    def get_rate(self) -> str:
        return settings.USER_PATH_THROTTLE_RATE

    def get_cache_key(self, request: HttpRequest) -> str:
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": f"{self.scope}-{request.path}",
            "ident": ident,
        }

    def throttle_failure(self) -> bool:
        logger = logging.getLogger(__name__)
        logger.error(f"UserPathRateThrottle error for {self.key}")
        return True


class _LoggingThrottleMixin:
    """
    Emits a structured error log with all the user/client data we have whenever
    a request is throttled. Relies on the throttle's ``get_cache_key`` having
    stashed the request on ``self._request`` (the only throttle hook that
    receives the request), so ``throttle_failure`` can read it back.
    """

    scope: str
    rate: str | None
    key: str | None

    def throttle_failure(self) -> bool:
        context = build_throttle_log_context(
            getattr(self, "_request", None),
            scope=self.scope,
            rate=self.rate,
            key=getattr(self, "key", None),
        )
        logger.error("Public API request throttled", extra=context)
        return super().throttle_failure()  # type: ignore[misc]


class PublicApiUserRateThrottle(_LoggingThrottleMixin, NinjaUserRateThrottle):
    """
    Enforced per-client throttle for the public ``developers_api``.

    Unlike ``NinjaUserPathRateThrottle`` (which only logs), this throttle
    actually blocks: ``allow_request`` returns ``False`` once the budget is
    exhausted, which makes django-ninja raise ``Throttled`` -> HTTP 429.
    On block it also logs an error with the full client context.

    The budget is global per client across all public endpoints (the cache key
    is NOT scoped by path), keyed by the authenticated user/OAuth-app/API-key
    identity. Anonymous traffic is handled separately by
    ``PublicApiAnonRateThrottle`` so this class only matches authenticated
    clients.
    """

    scope = "public_user"

    def get_rate(self) -> str:
        return settings.PUBLIC_API_USER_THROTTLE_RATE

    def get_cache_key(self, request: HttpRequest) -> str | None:
        self._request = request
        # Only throttle authenticated clients here; anonymous traffic is
        # covered by PublicApiAnonRateThrottle so the two never share a bucket.
        if not (request.user and request.user.is_authenticated):
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class PublicApiAnonRateThrottle(_LoggingThrottleMixin, NinjaAnonRateThrottle):
    """
    Enforced per-IP throttle for anonymous traffic on the public
    ``developers_api``. Stricter than the authenticated rate.

    Only applies to anonymous callers (returns ``None`` to skip throttling for
    authenticated ones), so it never double-counts with
    ``PublicApiUserRateThrottle``.

    NOTE: we key on ``request.user.is_authenticated`` rather than the base
    class's ``request.auth is not None`` check, because ``PublicAuth`` returns
    an ``AnonymousUser`` object (truthy, not ``None``) for anonymous traffic
    when ``ENABLE_ANONYMOUS_TRAFFIC`` is on -- the base check would wrongly
    treat that as authenticated and skip throttling entirely.
    """

    scope = "public_anon"

    def get_rate(self) -> str:
        return settings.PUBLIC_API_ANON_THROTTLE_RATE

    def get_cache_key(self, request: HttpRequest) -> str | None:
        self._request = request
        if request.user and request.user.is_authenticated:
            return None  # Authenticated clients are handled by the user throttle.

        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class DRFUserPathRateThrottle(DRFUserRateThrottle):
    scope = "user"

    def get_rate(self) -> str:
        return settings.USER_PATH_THROTTLE_RATE

    def get_cache_key(self, request, view) -> str:
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": f"{self.scope}-{request.path}",
            "ident": ident,
        }

    def throttle_failure(self) -> bool:
        logger = logging.getLogger(__name__)
        logger.error(f"UserPathRateThrottle error for {self.key}")
        return True
