from apps.core.ninja_utils.auth import public_auth
from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.error_handling import register_exception_handlers
from apps.core.ninja_utils.throttle import PublicApiAnonRateThrottle, PublicApiUserRateThrottle

from .ninja_api import assert_all_itqan_routers, create_ninja_api

# Rendered as the intro markdown at the top of the Scalar docs. Note that
# ``openapi_extra["info"]["description"]`` overrides the ``description=`` param,
# so the data blurb and the authentication guidance live together here.
_DEVELOPERS_API_DESCRIPTION = """\
REST API for Quranic recitation data — reciters, recitations, riwayat, qira'at, \
and ayah-level audio timings from verified publishers.

# Authentication

Itqan APIs use an API key to identify your application. Public read endpoints \
currently work without one, but we recommend creating a key now — it unlocks \
account-aware features, higher rate limits, and keeps your integration ready as \
authentication rolls out more widely.

## Get an API key

1. Sign in to the Asset Library at [cms.itqan.dev](https://cms.itqan.dev).
2. Open your account settings and go to **API Keys**.
3. Create a key, give it a descriptive name (e.g. `my-recitation-app`), and copy it.
4. Store it securely. Treat the key like a password — keep it in an environment \
variable or secret manager, never commit it to source control or expose it in \
client-side code.

Send the key in the `X-API-Key` header on each request.
"""

developers_api = create_ninja_api(
    title="Itqan CMS Public APIs",
    urls_namespace="",
    auth=public_auth,
    # Enforced global per-client throttling: authenticated clients and
    # anonymous (per-IP) traffic each get their own budget across all public
    # endpoints. Exceeding it returns HTTP 429.
    throttle=[PublicApiUserRateThrottle(), PublicApiAnonRateThrottle()],
    openapi_extra={"info": {"description": _DEVELOPERS_API_DESCRIPTION}},
)

register_exception_handlers(developers_api)

auto_discover_ninja_routers(developers_api, "api/public")

# Safety check: ensure routers are of type ItqanRouter
assert_all_itqan_routers(developers_api)
