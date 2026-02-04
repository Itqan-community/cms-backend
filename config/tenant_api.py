from django.contrib.admin.views.decorators import staff_member_required

from apps.core.ninja_utils.auth import ninja_jwt_auth_optional
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Tenant API (mounted at /tenant/)
tenant_api = create_ninja_api(
    title="Itqan CMS Tenant API",
    description="APIs for Tenant-specific operations",
    docs_base_path="/tenant",
    urls_namespace="tenant",
    auth=ninja_jwt_auth_optional,
    docs_decorator=staff_member_required,
)

# Register standard exception handlers
register_exception_handlers(tenant_api)

# Auto-discover routers from LOCAL_APPS under api/tenant
auto_discover_ninja_routers(tenant_api, "api/tenant")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(tenant_api)
