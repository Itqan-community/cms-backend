from collections.abc import Callable

from allauth.headless.contrib.ninja.security import XSessionTokenAuth
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from ninja_keys.auth import ApiKeyAuth
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication, JWTStatelessUserAuthentication

from apps.users.models import User


def make_optional(auth: Callable) -> Callable:
    """
    Wraps any auth instance so that a missing/invalid credential is accepted rather
    than rejected.  The request proceeds with AnonymousUser instead of failing.

    Usage:
        @router.get("/endpoint/", auth=make_optional(JWTAuth()))
        def my_view(request): ...
    """

    class _Optional:
        def __call__(self, request):
            result = auth(request)
            if result is not None:
                return result
            request.user = AnonymousUser()
            return None

    return _Optional()


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

public_auth = []
if settings.ENABLE_API_KEY_AUTH:
    public_auth.append(make_optional(ApiKeyAuth()))

if settings.ENABLE_OAUTH2:
    public_auth.append(OAuth2Auth())
else:
    public_auth.append(make_optional(OAuth2Auth()))


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
