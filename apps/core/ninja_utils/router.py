from collections.abc import Callable
from typing import Any

from ninja import Router
from ninja.constants import NOT_SET
from ninja.constants import NOT_SET_TYPE
from ninja.throttling import BaseThrottle
from ninja.types import TCallable
from ninja.utils import normalize_path

__all__ = ["ItqanRouter"]


class ItqanRouter(Router):
    def api_operation(
        self,
        methods: list[str],
        path: str,
        *,
        auth: Any = NOT_SET,
        throttle: BaseThrottle | list[BaseThrottle] | NOT_SET_TYPE = NOT_SET,
        response: Any = NOT_SET,
        operation_id: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        deprecated: bool | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        url_name: str | None = None,
        include_in_schema: bool = True,
        openapi_extra: dict[str, Any] | None = None,
    ) -> Callable[[TCallable], TCallable]:
        if not path.endswith("/"):
            raise ValueError("Path must end with /")
        if path.startswith("/"):
            raise ValueError("Path must not start with /")
        return super().api_operation(
            methods=methods,
            path=path,
            auth=auth,
            throttle=throttle,
            response=response,
            operation_id=operation_id,
            summary=summary,
            description=description,
            tags=tags,
            deprecated=deprecated,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            url_name=url_name,
            include_in_schema=include_in_schema,
            openapi_extra=openapi_extra,
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
