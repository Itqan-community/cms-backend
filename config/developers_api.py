from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Public Developers API instance (mount at /developers-api/)
developers_api = create_ninja_api(
    title="Itqan CMS Developers API",
    description="Itqan APIs for developers",
    docs_base_path="/developers-api-docs",
    urls_namespace="developers-api",
    auth=None,
)  # deprecated (keep for backward compatibility)
developers_api2 = create_ninja_api(
    title="Itqan CMS Developers API",
    description="Itqan APIs for developers",
    docs_base_path="/docs",
    urls_namespace="api",
    auth=None,
)
# Register standard exception handlers
register_exception_handlers(developers_api)
register_exception_handlers(developers_api2)

# Auto-discover routers from LOCAL_APPS under api/public
auto_discover_ninja_routers(developers_api, "api/public")
auto_discover_ninja_routers(developers_api2, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
assert_all_itqan_routers(developers_api2)
