from django.conf import settings
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
    JWTStatelessUserAuthentication,
)


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


class OAuth2OptionalAuth(OAuth2Auth):
    def __call__(self, request):
        ret = super().__call__(request)
        if ret is not None:
            return ret
        from django.contrib.auth.models import AnonymousUser

        anonymous_user = AnonymousUser()
        request.user = anonymous_user
        return anonymous_user


ninja_jwt_auth = [JWTAuth(), JWTAuthStateless()]
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
