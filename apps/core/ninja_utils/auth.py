from rest_framework_simplejwt.authentication import (
    JWTAuthentication,
    JWTStatelessUserAuthentication,
)

"""
Custom Connector for Django Ninja to use JWT authentication from djangorestframework-simplejwt.
"""


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


ninja_jwt_auth = [JWTAuth(), JWTAuthStateless()]


class OptionalJWTAuth:
    """Optional JWT authentication - allows both authenticated and anonymous users"""

    def __call__(self, request):
        # Try JWT authentication first
        for auth_method in ninja_jwt_auth:
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
