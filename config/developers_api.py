from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Public Developers API instance (mount at /developers-api/)
developers_api = create_ninja_api(
    title="Itqan CMS Developers API",
    description="Public APIs for external developers",
    docs_base_path="/developers-api",
    urls_namespace="developers-api",
    auth=None,
)

# Register standard exception handlers
register_exception_handlers(developers_api)

# Auto-discover routers from LOCAL_APPS under api/public
auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
