from typing import Literal

from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import Developer, User

from ._schemas import RegisterSchema, TokenResponseSchema

router = ItqanRouter(tags=[NinjaTag.AUTH])

if not settings.ENABLE_ALLAUTH:

    @router.post(
        "auth/register/",
        auth=None,
        response={
            200: TokenResponseSchema,
            400: NinjaErrorResponse[Literal["registration_failed"], Literal[None]],
        },
        summary="Register",
        description="Register new user with email and password",
    )
    def register_user(request: Request, registration_data: RegisterSchema):
        """Register new user"""
        # Check if user already exists
        if User.objects.filter(email=registration_data.email).exists():
            raise ItqanError(
                error_name="email_already_exists",
                message="User with this email already exists",
                status_code=400,
            )

        try:
            # Create new user
            user = User.objects.create_user(
                email=registration_data.email,
                password=registration_data.password,
                name=registration_data.name,
                phone=registration_data.phone,
                is_active=True,
            )

            from django import forms

            f = forms.EmailField()
            f.clean(registration_data.email)  # raise ValidationError if invalid, which will be turned into ItqanError

            # Auto-create developer profile for the user
            developer_profile, _ = Developer.objects.get_or_create(
                user=user, defaults={"job_title": registration_data.job_title}
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
                    "phone": str(user.phone) if user.phone else "",
                    "is_active": user.is_active,
                    "created": True,
                    "is_profile_completed": developer_profile.profile_completed,
                },
            }
        except Exception as e:
            raise ItqanError(
                error_name="registration_failed",
                message=f"Registration failed: {str(e)}",
                status_code=400,
            ) from e
