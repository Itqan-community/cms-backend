from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

portal_api = create_ninja_api(
    title="Itqan Portal API",
    description="Portal APIs for admin management",
    docs_base_path="/portal-api",
    urls_namespace="portal-api",
    auth=ninja_jwt_auth,
)

register_exception_handlers(portal_api)

auto_discover_ninja_routers(portal_api, "api/portal")

assert_all_itqan_routers(portal_api)
