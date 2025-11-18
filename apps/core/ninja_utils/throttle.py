import logging

from django.conf import settings
from django.http import HttpRequest
from ninja.throttling import UserRateThrottle as NinjaUserRateThrottle
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
