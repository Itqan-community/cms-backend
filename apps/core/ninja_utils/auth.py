import hashlib

from allauth.headless.contrib.ninja.security import JWTTokenAuth, jwt_token_auth
from django.conf import settings
from django.core.cache import cache
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import JWTAuthentication, JWTStatelessUserAuthentication

_OAUTH2_CACHE_TTL = 60  # seconds — short enough that revoked tokens expire quickly


class JWTAuth(JWTAuthentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        return res


class JWTAuthStaff(JWTAuthentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        if not request.user.is_staff and not request.user.is_superuser:
            return None
        return res


class JWTAllAuthStaff(JWTTokenAuth):
    def __call__(self, request):
        res = super().__call__(request)
        if res is None:
            return None
        if not request.user.is_staff and not request.user.is_superuser:
            return None
        return res


class JWTAuthStateless(JWTStatelessUserAuthentication):
    def __call__(self, request):
        res = self.authenticate(request)
        if res is None:
            return None
        request.user = res[0]
        return res


def _extract_bearer(request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


class OAuth2Auth(OAuth2Authentication):
    def __call__(self, request):
        bearer = _extract_bearer(request)
        if bearer:
            cache_key = f"oauth2_auth:{hashlib.sha256(bearer.encode()).hexdigest()}"
            cached = cache.get(cache_key)
            if cached is not None:
                from django.contrib.auth import get_user_model
                from oauth2_provider.models import AccessToken

                try:
                    user_pk, token_pk = cached
                    User = get_user_model()
                    user = User.objects.get(pk=user_pk)
                    token = AccessToken.objects.select_related("application__user").get(pk=token_pk)
                    request.user = user
                    request.access_token = token
                    return (user, token)
                except Exception:
                    cache.delete(cache_key)

        res = self.authenticate(request)
        if res is None:
            return None
        user, token = res
        request.user = user
        request.access_token = token

        if bearer and token is not None:
            cache.set(cache_key, (user.pk, token.pk), _OAUTH2_CACHE_TTL)

        return res


class OAuth2OptionalAuth(OAuth2Auth):
    def __call__(self, request):
        ret = super().__call__(request)
        if ret is not None:
            return ret
        from django.contrib.auth.models import AnonymousUser

        anonymous_user = AnonymousUser()
        request.user = anonymous_user
        return anonymous_user


if settings.ENABLE_ALLAUTH:
    ninja_jwt_auth = [jwt_token_auth]
    ninja_jwt_staff_auth = JWTAllAuthStaff()
else:
    ninja_jwt_auth = [JWTAuth(), JWTAuthStateless()]
    ninja_jwt_staff_auth = JWTAuthStaff()
if settings.ENABLE_OAUTH2:
    ninja_oauth2_auth = [OAuth2Auth()]
else:
    ninja_oauth2_auth = [OAuth2OptionalAuth()]


class OptionalJWTAuth:
    """Optional JWT authentication - allows both authenticated and anonymous users"""

    def __call__(self, request):
        # Try JWT authentication first
        for auth_method in ninja_jwt_auth + ninja_oauth2_auth:
            result = auth_method(request)
            if result is not None:
                return result

        # If no JWT authentication succeeds, allow anonymous access
        # We need to return a user object, so use AnonymousUser
        from django.contrib.auth.models import AnonymousUser

        anonymous_user = AnonymousUser()
        request.user = anonymous_user
        return anonymous_user


ninja_jwt_auth_optional = OptionalJWTAuth()
