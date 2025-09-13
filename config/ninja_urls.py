from ninja import NinjaAPI

from apps.core.ninja_utils.autodiscover import auto_discover_ninja_routers
from apps.core.ninja_utils.parser import NinjaParser
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.throttle import NinjaUserPathRateThrottle

# from apps.ninja_authentication import NinjaAuth


ninja_api = NinjaAPI(
    # auth=NinjaAuth(),
    default_router=ItqanRouter(),
    throttle=NinjaUserPathRateThrottle(),
    parser=NinjaParser(),
    # docs_decorator=staff_member_required,
)

from apps.core.ninja_utils.error_handling import *  # noqa f401

# ninja_api.add_router("/", "apps.users.views.activation_user_account_request.router")
auto_discover_ninja_routers(ninja_api, "views")

if not all(isinstance(r[1], ItqanRouter) for r in ninja_api._routers):
    raise Exception("All routers must be of type ItqanRouter")
