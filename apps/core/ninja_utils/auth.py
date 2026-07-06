from allauth.headless.contrib.ninja.security import XSessionTokenAuth
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from ninja_keys.auth import ApiKeyAuth as BaseApiKeyAuth
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication, JWTStatelessUserAuthentication

from apps.users.models import User


class JWTAuth(JWTAuthentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        return res


class JWTAuthStateless(JWTStatelessUserAuthentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        return res


class OAuth2Auth(OAuth2Authentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        return res


class SessionToken(XSessionTokenAuth):
    def __call__(self, request):
        res: User | None = super().__call__(request)
        if res is None:
            return None
        request.user = res
        return res


if settings.ENABLE_ALLAUTH:
    internal_auth = [SessionToken()]
else:
    internal_auth = [JWTAuth(), JWTAuthStateless()]


class ApiKeyAuth(BaseApiKeyAuth):
    """API key auth that binds the key's owner to ``request.user``.

    The upstream ``ApiKeyAuth.authenticate`` only returns a boolean, so the
    consumer identity is lost. Per-asset access checks (access requests) need the
    actual user, so we resolve the key to its owner and set ``request.user``.
    """

    def authenticate(self, request, key):
        if not key:
            return None
        model = self.model
        try:
            api_key = model.objects.get_from_key(key)
        except model.DoesNotExist:
            return None
        if api_key.has_expired:
            return None
        request.user = api_key.user
        return api_key.user


class PublicAuth:
    openapi_security_schema: dict = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API key issued for your Application, sent in the X-API-Key header.",
    }

    def __call__(self, request):
        methods = []
        if settings.ENABLE_API_KEY_AUTH:
            methods.append(ApiKeyAuth())
        if settings.ENABLE_OAUTH2:
            methods.append(OAuth2Auth())
        for auth_method in methods:
            result = auth_method(request)
            if result is not None:
                return result
        if settings.ENABLE_ANONYMOUS_TRAFFIC:
            anonymous_user = AnonymousUser()
            request.user = anonymous_user
            return anonymous_user
        return None


public_auth = [PublicAuth()]


class _OptionalAllAuth:
    """Tries every configured auth method; falls back to AnonymousUser."""

    def __call__(self, request):
        for auth_method in internal_auth + public_auth:
            result = auth_method(request)
            if result is not None:
                return result
        anonymous_user = AnonymousUser()
        request.user = anonymous_user
        return anonymous_user


optional_auth = _OptionalAllAuth()
