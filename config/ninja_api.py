from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ninja import NinjaAPI
from ninja.throttling import BaseThrottle
from ninja.types import TCallable
from scalar_ninja import ScalarViewer

from apps.core.ninja_utils.parser import NinjaParser
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.throttle import NinjaUserPathRateThrottle


def create_ninja_api(
    *,
    title: str,
    description: str | None = None,
    auth=None,
    docs_base_path: str = "",
    default_router: ItqanRouter | None = None,
    enable_throttle: bool = True,
    throttle: BaseThrottle | list[BaseThrottle] | None = None,
    enable_parser: bool = True,
    urls_namespace: str | None = None,
    docs_decorator: Callable[[TCallable], TCallable] | None = None,
    openapi_extra: dict[str, Any] | None = None,
) -> NinjaAPI:
    """
    Factory to create a NinjaAPI instance with Itqan defaults.

    ``throttle`` lets a caller supply its own throttle(s) (e.g. the public
    ``developers_api`` uses enforcing per-client throttles). When omitted and
    ``enable_throttle`` is True, the default non-enforcing
    ``NinjaUserPathRateThrottle`` is used.
    """
    router = default_router or ItqanRouter()
    if not enable_throttle:
        throttle = None
    elif throttle is None:
        throttle = NinjaUserPathRateThrottle()
    parser = NinjaParser() if enable_parser else None

    api = NinjaAPI(
        title=title,
        description=description,
        auth=auth,
        default_router=router,
        throttle=throttle,
        parser=parser,
        docs=ScalarViewer(openapi_url=f"{docs_base_path}/openapi.json", hide_models=True),
        docs_url="/docs/",
        urls_namespace=urls_namespace,
        docs_decorator=docs_decorator,
        openapi_extra=openapi_extra,
    )

    return api


def assert_all_itqan_routers(api: NinjaAPI) -> None:
    if not all(isinstance(r[1], ItqanRouter) for r in api._routers):
        raise Exception("All routers must be of type ItqanRouter")
