from typing import Dict
from django.http import HttpRequest
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.tags import NinjaTag
from apps.users.models import User
from ._schemas import RefreshTokenSchema

router = ItqanRouter(tags=[NinjaTag.AUTH])


@router.post(
    "auth/token/refresh/",
    response={200: Dict[str, str]},
    summary="Refresh JWT access token",
    description="Refresh expired JWT access token using refresh token"
)
def refresh_token(request: HttpRequest, refresh_data: RefreshTokenSchema):
    """Refresh JWT access token"""
    try:
        # Use rest_framework_simplejwt to refresh token
        refresh = RefreshToken(refresh_data.refresh)
        access = refresh.access_token
        
        response = {"access": str(access)}
        
        # If rotation is enabled, return new refresh token
        if getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS', False):
            try:
                refresh.blacklist()
                # Get user from token payload
                user_id = refresh.payload.get('user_id')
                user = User.objects.get(id=user_id)
                new_refresh = RefreshToken.for_user(user)
                response["refresh"] = str(new_refresh)
            except Exception as e:
                raise ItqanError(
                    error_name="token_rotation_failed",
                    message=f"Failed to rotate refresh token: {str(e)}",
                    status_code=500
                )
        
        return response
    except (InvalidToken, TokenError) as e:
        raise ItqanError(
            error_name="invalid_refresh_token",
            message="Invalid or expired refresh token",
            status_code=401
        )
    except User.DoesNotExist:
        raise ItqanError(
            error_name="user_not_found",
            message="User associated with token not found",
            status_code=401
        )
