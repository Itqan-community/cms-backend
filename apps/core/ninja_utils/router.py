from collections.abc import Callable
from typing import Any

from ninja import Router
from ninja.constants import NOT_SET, NOT_SET_TYPE
from ninja.throttling import BaseThrottle
from ninja.types import TCallable
from ninja.utils import normalize_path

__all__ = ["ItqanRouter"]

from apps.core.ninja_utils.auth import ninja_jwt_auth_optional


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
            raise ValueError("Path must end with /")
        if path.startswith("/"):
            raise ValueError("Path must not start with /")
        return super().api_operation(
            methods=methods,
            path=path,
            auth=ninja_jwt_auth_optional if auth is None else auth,
            throttle=throttle,
            response=response,
            **kwargs,
        )

    def build_routers(self, prefix: str) -> list[tuple[str, "Router"]]:
        # This Code hide errors and show incorrect error

        # if self.api is not None:
        # from ninja.main import debug_server_url_reimport
        #
        # if not debug_server_url_reimport():
        #     raise ConfigError(
        #         f"Router@'{prefix}' has already been attached to API" f" {self.api.title}:{self.api.version} "
        #     )
        internal_routes = []

        for inter_prefix, inter_router in self._routers:
            _route = normalize_path(f"{prefix}/{inter_prefix}").lstrip("/")
            internal_routes.extend(inter_router.build_routers(_route))
        return [(prefix, self), *internal_routes]
