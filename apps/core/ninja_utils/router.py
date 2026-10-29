from collections.abc import Callable
from typing import Any

from django.utils.translation import gettext_lazy as _
from ninja import Router
from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.throttling import BaseThrottle
from ninja.types import TCallable

__all__ = ["ItqanRouter"]

from apps.core.ninja_utils.auth import optional_auth


class ItqanRouter(Router):
    """
    This Router is made to enforce some rules about paths, and how auth is handled.
    """

    def api_operation(
        self,
        methods: list[str],
        path: str,
        auth: Any = NOT_SET,
        throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
        response: Any = NOT_SET,
        **kwargs: Any,
    ) -> Callable[[TCallable], TCallable]:
        if not path.endswith("/"):
            raise ValueError(_("Path must end with /"))
        if path.startswith("/"):
            raise ValueError(_("Path must not start with /"))
        return super().api_operation(
            methods=methods,
            path=path,
            auth=optional_auth if auth is None else auth,
            throttle=throttle,
            response=response,
            **kwargs,
        )
