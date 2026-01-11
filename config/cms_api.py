from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required

from apps.core.ninja_utils.auth import ninja_jwt_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Internal CMS API (mounted at /cms-api/)
cms_api = create_ninja_api(
    title="Itqan CMS Internal API",
    description="Internal APIs for CMS frontend",
    docs_base_path="/cms-api",
    urls_namespace="cms-api",
    auth=ninja_jwt_auth,
    docs_decorator=staff_member_required,
)
if settings.ENABLE_ALLAUTH:
    cms_api.openapi_extra = {
        "info": {
            "description": "# Authentication\n\n"
            "## Authentication docs\n\n"
            "Authentication supports many features, and it has its own extensive documentation.\n\n"
            "You can find authentication documentation [Here](../cms-api/auth/docs)",
        }
    }


# Register standard exception handlers
register_exception_handlers(cms_api)

# Auto-discover routers from LOCAL_APPS under api/internal
auto_discover_ninja_routers(cms_api, "api/internal")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(cms_api)
cms_auth_api = create_ninja_api(
    title="Itqan CMS Internal Auth API",
    description="Internal APIs for CMS frontend",
    docs_base_path="/cms-api/auth",
    urls_namespace="cms-api-auth",
    auth=ninja_jwt_auth,
    docs_decorator=staff_member_required,
)

# Register standard exception handlers
register_exception_handlers(cms_auth_api)
