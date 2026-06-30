from apps.core.ninja_utils.auth import public_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers
from apps.core.ninja_utils.throttle import PublicApiAnonRateThrottle, PublicApiUserRateThrottle

from .ninja_api import assert_all_itqan_routers, create_ninja_api

developers_api = create_ninja_api(
    title="Itqan CMS Public APIs",
    description=(
        "REST API for Quranic recitation data — reciters, recitations, "
        "riwayat, qira'at, and ayah-level audio timings from verified publishers."
    ),
    urls_namespace="",
    auth=public_auth,
    # Enforced global per-client throttling: authenticated clients and
    # anonymous (per-IP) traffic each get their own budget across all public
    # endpoints. Exceeding it returns HTTP 429.
    throttle=[PublicApiUserRateThrottle(), PublicApiAnonRateThrottle()],
)

register_exception_handlers(developers_api)

auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
