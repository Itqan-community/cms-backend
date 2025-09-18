from django.contrib.auth import authenticate
from django.http import HttpRequest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import User
from ._schemas import LoginSchema, TokenResponseSchema
from ...core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.AUTH])


@router.post(
    "auth/login/",
    auth=None,
    response=TokenResponseSchema,
    description="Authenticate user with email and password, returns JWT tokens"
)
def login_user(request: Request, credentials: LoginSchema):
    """Login user with email and password"""
    user :User|None = authenticate(request, username=credentials.email, password=credentials.password)
    
    if user is None:
        raise ItqanError(
            error_name="invalid_credentials",
            message="Invalid email or password",
            status_code=401
        )
    
    if not user.is_active:
        raise ItqanError(
            error_name="account_disabled",
            message="Account is disabled",
            status_code=401
        )
    
    # Generate JWT tokens using rest_framework_simplejwt
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    
    return {
        "access": str(access),
        "refresh": str(refresh),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "is_active": user.is_active,
        }
    }
