from apps.core.ninja_utils.auth import ninja_jwt_auth, ninja_oauth2_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

deprecated_developers_api = create_ninja_api(
    title="Itqan CMS Developers API (Deprecated)",
    description="Itqan APIs for developers",
    urls_namespace="developers-api",
    docs_base_path="/developers-api",
    auth=ninja_jwt_auth + ninja_oauth2_auth,
)  # deprecated (keep for backward compatibility)
developers_api = create_ninja_api(
    title="Itqan CMS Developers API",
    description="Itqan APIs for developers",
    urls_namespace="",
    auth=ninja_jwt_auth + ninja_oauth2_auth,
)

register_exception_handlers(deprecated_developers_api)
register_exception_handlers(developers_api)

auto_discover_ninja_routers(deprecated_developers_api, "api/public")
auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(deprecated_developers_api)
assert_all_itqan_routers(developers_api)
