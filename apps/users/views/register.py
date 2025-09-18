from django.http import HttpRequest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import User
from ._schemas import RegisterSchema, TokenResponseSchema

router = ItqanRouter(tags=[NinjaTag.AUTH])


@router.post(
    "auth/register/",
auth=None,
    response=TokenResponseSchema,
    summary="Register",
    description="Register new user with email and password"
)
def register_user(request: HttpRequest, registration_data: RegisterSchema):
    """Register new user"""
    # Check if user already exists
    if User.objects.filter(email=registration_data.email).exists():
        raise ItqanError(
            error_name="email_already_exists",
            message="User with this email already exists",
            status_code=400
        )
    
    try:
        # Create new user
        user = User.objects.create_user(
            email=registration_data.email,
            password=registration_data.password,
            name=registration_data.name,
            is_active=True
        )
        
        # Generate JWT tokens
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
                "created": True
            }
        }
    except Exception as e:
        raise ItqanError(
            error_name="registration_failed",
            message=f"Registration failed: {str(e)}",
            status_code=400
        )
