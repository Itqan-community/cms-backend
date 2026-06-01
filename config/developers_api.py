from apps.core.ninja_utils.auth import public_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers

from .ninja_api import assert_all_itqan_routers, create_ninja_api

developers_api = create_ninja_api(
    title="Itqan CMS Public APIs",
    description=(
        "REST API for Quranic recitation data — reciters, recitations, "
        "riwayat, qira'at, and ayah-level audio timings from verified publishers."
    ),
    urls_namespace="",
    auth=public_auth,
)

register_exception_handlers(developers_api)

auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
