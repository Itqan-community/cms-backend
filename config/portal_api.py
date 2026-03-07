from django.conf import settings

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Internal CMS API (mounted at /cms-api/)
portal_api = create_ninja_api(
    title="Itqan CMS Internal API for admins to controls resources",
    description="Internal APIs for CMS frontend, this API is meant for admins to controls resources",
    docs_base_path="/portal",
    urls_namespace="portal",
    auth=ninja_jwt_auth,
)
if settings.ENABLE_ALLAUTH:
    portal_api.openapi_extra = {
        "info": {
            "description": "# Authentication\n\n"
            "## Authentication docs\n\n"
            "Authentication supports many features, and it has its own extensive documentation.\n\n"
            "You can find authentication documentation [Here](../cms-api/auth/docs)",
        }
    }


register_exception_handlers(portal_api)

auto_discover_ninja_routers(portal_api, "api/portal")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(portal_api)
portal_auth_api = create_ninja_api(
    title="Itqan CMS Internal Auth API",
    description="Internal APIs for CMS frontend",
    docs_base_path="/portal/auth",
    urls_namespace="portal-auth",
    auth=ninja_jwt_auth,
)

# Register standard exception handlers
register_exception_handlers(portal_auth_api)
