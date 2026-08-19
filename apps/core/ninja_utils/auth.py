from allauth.headless.contrib.ninja.security import XSessionTokenAuth
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.translation import gettext_lazy as _
from ninja.errors import AuthenticationError
from ninja_keys.auth import ApiKeyAuth as BaseApiKeyAuth
from oauth2_provider.contrib.rest_framework import OAuth2Authentication

from apps.users.models import User


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


internal_auth = [SessionToken()]


class ApiKeyAuth(BaseApiKeyAuth):
    """API key auth that binds the key's owner to ``request.user``.

    The resolved ``APIKey`` itself is returned so Django Ninja exposes it as
    ``request.auth``. Usage tracking can then use the key's non-secret prefix for
    per-app attribution without re-resolving the raw X-API-Key header.
    ``request.user`` is still set to the key's owner for per-asset access checks
    and user-scoped permissions.
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
            raise AuthenticationError(message=str(_("API key has expired.")))

        request.user = api_key.user
        return api_key


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
