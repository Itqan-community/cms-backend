from __future__ import annotations

from ninja import NinjaAPI
from scalar_django_ninja import ScalarViewer

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
    enable_parser: bool = True,
    urls_namespace: str | None = None,
) -> NinjaAPI:
    """
    Factory to create a NinjaAPI instance with Itqan defaults.

    docs_base_path controls openapi_url
    (e.g. '/cms-api' or '/developers-api').
    """
    router = default_router or ItqanRouter()
    throttle = NinjaUserPathRateThrottle() if enable_throttle else None
    parser = NinjaParser() if enable_parser else None

    api = NinjaAPI(
        title=title,
        description=description,
        auth=auth,
        default_router=router,
        throttle=throttle,
        parser=parser,
        docs=ScalarViewer(openapi_url=f"{docs_base_path}/openapi.json"),
        docs_url="/docs/",
        urls_namespace=urls_namespace,
    )
    return api


def assert_all_itqan_routers(api: NinjaAPI) -> None:
    if not all(isinstance(r[1], ItqanRouter) for r in api._routers):
        raise Exception("All routers must be of type ItqanRouter")
