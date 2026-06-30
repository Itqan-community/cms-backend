import logging

from django.conf import settings
from django.http import HttpRequest
from ninja.throttling import AnonRateThrottle as NinjaAnonRateThrottle, UserRateThrottle as NinjaUserRateThrottle
from rest_framework.throttling import UserRateThrottle as DRFUserRateThrottle


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


class PublicApiUserRateThrottle(NinjaUserRateThrottle):
    """
    Enforced per-client throttle for the public ``developers_api``.

    Unlike ``NinjaUserPathRateThrottle`` (which only logs), this throttle
    actually blocks: ``allow_request`` returns ``False`` once the budget is
    exhausted, which makes django-ninja raise ``Throttled`` -> HTTP 429.

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
        # Only throttle authenticated clients here; anonymous traffic is
        # covered by PublicApiAnonRateThrottle so the two never share a bucket.
        if not (request.user and request.user.is_authenticated):
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class PublicApiAnonRateThrottle(NinjaAnonRateThrottle):
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
