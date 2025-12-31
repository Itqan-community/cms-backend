from django.conf import settings
from django.http import HttpRequest, HttpResponseBase
from django.views.decorators.csrf import csrf_exempt
from ninja import Schema
from oauth2_provider.views import AuthorizationView, RevokeTokenView, TokenView

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.USERS])


class OAuth2AuthorizeResponseSchema(Schema):
    authorization_url: str
    state: str


class Oauth2TokenResponseSchema(Schema):
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str


if settings.ENABLE_OAUTH2:

    @router.post("token/", response=Oauth2TokenResponseSchema, auth=None)
    @csrf_exempt
    def token_endpoint(request: HttpRequest) -> HttpResponseBase:
        """
        OAuth2 Token Endpoint.
        Supports: authorization_code, password, client_credentials, refresh_token.
        Requires client credentials in the Authorization: Basic header.
        """
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

    @router.api_operation(["GET", "POST"], "authorize/", auth=None)
    def authorize_endpoint(request: HttpRequest) -> HttpResponseBase:
        """
        OAuth2 Authorization Endpoint.
        Supports: code.
        Requires user to be logged in (SessionAuthentication).
        """
        view = AuthorizationView.as_view()
        return view(request)
