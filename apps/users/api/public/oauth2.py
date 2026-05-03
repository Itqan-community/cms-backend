from django.conf import settings
from django.http import HttpRequest, HttpResponseBase
from django.views.decorators.csrf import csrf_exempt
from ninja import Schema
from oauth2_provider.views import RevokeTokenView, TokenView

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.USERS])


class Oauth2TokenResponseSchema(Schema):
    access_token: str
    expires_in: int
    token_type: str


if settings.ENABLE_OAUTH2:

    @router.post("token/", response=Oauth2TokenResponseSchema, auth=None)
    @csrf_exempt
    def token_endpoint(request: HttpRequest) -> HttpResponseBase:
        """
        OAuth2 Token Endpoint.
        Supports: client_credentials only. grant_type is always enforced as client_credentials.
        Requires client credentials in the Authorization: Basic header.
        """
        request.POST = request.POST.copy()
        request.POST["grant_type"] = "client_credentials"
        view = TokenView.as_view()
        return view(request)

    @router.post("revoke/", auth=None)
    @csrf_exempt
    def revoke_endpoint(request: HttpRequest) -> HttpResponseBase:
        """
        OAuth2 Token Revocation Endpoint.
        Requires client credentials in the Authorization: Basic header.
        """
        view = RevokeTokenView.as_view()
        return view(request)
