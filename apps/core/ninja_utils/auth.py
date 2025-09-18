from rest_framework_simplejwt.authentication import JWTAuthentication, JWTStatelessUserAuthentication


class JWTAuth(JWTAuthentication):


    def __call__(self, request):

        ret  = self.authenticate(request)
        if ret is None:
            return None
        request.user = ret[0]
        return ret


class JWTAuthStateless(JWTStatelessUserAuthentication):

    def __call__(self, request):
        ret = self.authenticate(request)
        if ret is None:
            return None
        request.user = ret[0]
        return ret


ninja_jwt_auth = [JWTAuth(), JWTAuthStateless()]